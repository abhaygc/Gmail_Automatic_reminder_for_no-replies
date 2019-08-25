import sys
import imaplib
import email
import email.header
import datetime
import os
import pymongo
import re

#EMAIL_FOLDER contains path of directory to store the attachments
#Attachments are stored in this directory
#We create folder for each mail with name subject+emailid of sender and place all attachments under that
EMAIL_FOLDER = "your_attachment_dir"
if not os.path.exists(EMAIL_FOLDER):
    os.mkdir(EMAIL_FOLDER)

M = None
no_replies_dict=[]

#This function creates DB if not already in place
def dbcreate():
    global email_sent,email_inbox
    now = datetime.datetime.now()
    myclient = pymongo.MongoClient("mongodb://localhost:27017/")
    if "EmailDB" not in myclient.list_database_names():
        emaildb = myclient["EmailDB"]
        email_sent = emaildb["emails_sent"]
        email_inbox = emaildb["emails_inbox"]
        email_sent.insert_one({'Date_Created':now.isoformat()})
        email_inbox.insert_one({'Date_Created':now.isoformat()})
    else:
        emaildb = myclient["EmailDB"]
        email_sent = emaildb["emails_sent"]
        email_inbox = emaildb["emails_inbox"]
        emaildb.drop_collection(email_inbox)
        email_inbox = emaildb["emails_inbox"]
        email_inbox.insert_one({'Date_Created':now.isoformat()})
    return email_sent, email_inbox


def main(EMAIL_ACCOUNT,EMAIL_PASSWORD ):
    global M,no_replies_dict,start,email_sent, email_inbox

    email_sent, email_inbox = dbcreate()

    #creating a IMAP4_SSL object for connection
    M = imaplib.IMAP4_SSL('imap.gmail.com')

    #To list of emails who have not replied
    no_replies_dict=[]

    try:
        #Logging to the account
        M.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
    except imaplib.IMAP4.error:
        print ("LOGIN FAILED!!! ")
        sys.exit(1)

    #Seelcting the 'INBOX' mailbox
    #select() returns tuple consisting Response code and Number of messages in the Mailbox
    rv, data = M.select("INBOX")

    #Checking response code if there was any error
    if rv == 'OK':
        #processing the emails of the 'INBOX' mailbox
        process_mailbox(M,no_replies_dict)

        #Closing the selected mailbox i.e. 'INBOX'
        M.close()

    else:
        print("ERROR: Unable to open mailbox ", rv)

    #Logout from the account
    M.logout()

    #return the list of emails who have not replied
    return no_replies_dict

def process_mailbox(M,no_replies_dict):

    global email_sent, email_inbox

    #search() method accepts two parameters
    #1. Charset : to sepecify the charset to the email server. If no specific use None.
    #2. Criterion : Multiple criterias can be provided as per RFC guildlines
    #We use search to get all mails of the 'INBOX' mailbox
    #search() returns tuple of response code and list of idenetifiers of the mails satisfying the criteria
    rv, data = M.search(None, "ALL")

    if rv != 'OK':
        print("No messages found!")
        return

    #We traverse through all identifiers returned by the search() method
    for num in data[0].split():
        #fetch() accepts 2 parameters
        #1. Identifier of the message
        #2. Which part to extract
            #We RFC standard 'RFC822' to extract whole email message
        #fetch() returns tuple of response code and list containing message
        rv, data = M.fetch(num, '(RFC822)')

        if rv != 'OK':
            print("ERROR getting message", num)
            return

        #Generating email Mesaage from the output of fetch()
        #msg belongs to class email.Message
        msg = email.message_from_bytes(data[0][1])

        #Using decode_header() to get various header details

        #Getting subject
        subject = email.header.decode_header(msg['Subject'])[0][0]

        #Getting from
        FRM = email.header.decode_header(msg['From'])[0][0]

        #Extracting Email ID mentioned inside '<>'
        FRM = (re.findall(r'\<(.+?)\>',FRM))[0]

        #Getting Message ID of the email
        msgID = email.header.decode_header(msg['Message-ID'])[0][0]

        #Checking if the mail is reply to any email if yes store the In-Reply-To header
        #In-Reply-To header consists MessageID of email to which the reply the reply mail is meant for
        try:
            inReply = email.header.decode_header(msg['In-Reply-To'])[0][0]
        except:
            inReply="No IN-REPLY"


        #Getting email content
        msgContent = get_body(msg)

        #Getting attachments
        get_attachments(msg,subject,FRM)


        # Getting date-time of email
        date_tuple = email.utils.parsedate_tz(msg['Date']) #returns a tupe containing date parameters like year month date hours minutes
        if date_tuple:
            local_date = datetime.datetime.fromtimestamp(email.utils.mktime_tz(date_tuple))
            #Storing the date in local_timezone


        #Insert Email details in the DB
        email_inbox.insert_one(
                {
                    'from':FRM,
                    'subject':subject,
                    'date':local_date,
                    'message':msgContent,
                    'hasAttachments':has_attachments(msg),
                    'inReply':inReply,
                    'messageID':msgID
                }
            )

    #Now we check for the emails who have not replied yet
    chk_no_replies(no_replies_dict)


def chk_no_replies(no_replies_dict):

    #creating query to check emails sent through our system and are not reminder
    #Also will creating Databse we insert a document with datetime of that instant
    #We need to skip that document so we use "subject": {"$exists": True} in our query
    #because that document doesn't have subject field
    query = {"subject": {"$exists": True},"is_reminder":0}

    for x in email_sent.find(query):
        #Getting required paramters of the mails
        sub = "Re: "+x['subject']
        msgID = x['MessageID']

        #creating a empty list to store only email ids of recipients who haven't replied
        no_replies_email_id=[]

        #We iterate through reminder dictionary we created for each recipient while sending the mail
        for i in x['reminder']:
            #Getting email of recipient
            mail = i["id"]

            #Checking if the recipient has replied
            query2 = {"subject": {"$exists": True},"from":mail,'inReply':msgID, "subject": sub}
            chk = email_inbox.find_one(query2)


            if chk == None:
                #It neans the recipient hasn't replied
                #We append details of reminder for the recipient to the list
                no_replies_dict.append({'id':mail,'remdatetime':i['remdatetime'],\
                                        'resub':i['resub'],
                                       'remsg':i['remsg'],'remsms':i['remsms'],'timestamp':i['timestamp'],\
                                       'subject':x['subject'],'sentDate':x['DateTime'],\
                                      'remnumbers':x['reminder_numbers'],'remmails':x['reminder_mails']})
                #Append to list of no replies list
                no_replies_email_id.append(mail)

        #If we want the email ids of those who replied
        #We apply basic set theory
        #The difference of all the recipients and those who ot replied is those who replied
        replied_email_id =list(set(x['to'])-set(no_replies_email_id))




#Used to get main email body
def get_body(msg):
    #We may recieve a Multipart mail
    #So we need to find the main email content part which is generally the first payload in a multipart email
    #We check if the currrent part/mail is mulipart. If yes then we check inside it

    #If message is a list of parts then
    # get_payload() 's first parameter is to define index of part we are looking to extract.
    # But if it is a string then index cannot be passed so we pass None
    #second parameter is 'decode'. We should set it to 'True' if we want the message to be decoded as specified in mail header
    if msg.is_multipart():
        return get_body(msg.get_payload(0))
    else:
        #Here when we get the main email part we extract it using get_payload()
        #we decode the email body in 'utf-8' charset
        return msg.get_payload(decode=True).decode("utf-8")

#Explaination for getting attachments used in below 2 functions has_attachments() and get_attachments
#walk() method of Message class can be used to traverse all the subparts of the mesaage
#We traverse the message until we find a part which is not of type multipart
#The part not of type multipart can be either 1. Email Text content or 2. Attachment
#So we  also check 'Content-Diposition' header  if is None it might me email body so skip it
#Finally we get attachments out of the Message parts

#has_attachments() is used to check whether a email has attachments or not.
#This can be useful in case you need to display any sign for presence of attachments
#Also we store this value in database
def has_attachments(msg):
    for part in msg.walk():
        if part.get_content_maintype()=='multipart':
            continue
        if part.get('Content-Disposition') is None:
            continue
        fileName = part.get_filename()

        if bool(fileName):
            return 1
        else:
            return 0

#get_attachments() extracts the attachments from the Message
def get_attachments(msg,subject,FRM):
    for part in msg.walk():
        if part.get_content_maintype()=='multipart':
            continue
        if part.get('Content-Disposition') is None:
            continue

        fileName = part.get_filename()

        if bool(fileName):
            #Creating folder path
            folder = os.path.join(EMAIL_FOLDER,subject+'_'+FRM)
            if not os.path.exists(folder):
                os.mkdir(folder)
            filePath = os.path.join(folder, fileName)
            with open(filePath,'wb') as f:
                f.write(part.get_payload(decode=True))

#get_attachments_now() can be used to extract attachments of a single email on dynamic demand
#This function accepts the MessageID as the parameter
#Using Search method of IMAP class we access the particular mail directly
#We pass message,subject,sender id to get_attachments() to download the attachments
def get_attachments_now(msgID,subject,FRM):
    type, data = M.search(None, '(HEADER Message-ID "%s")' % msgID)

    #search() returns list of identifiers for mail satisfying the search
    #But since Message-ID is unique we only have one identifier
    num = data[0]

    rv, data = M.fetch(num, '(RFC822)')

    if rv != 'OK':
        print("ERROR getting message", num)
        return

    msg = email.message_from_bytes(data[0][1])
    get_attachments(msg,subject,FRM)



if __name__ == '__main__':

    #Set email id of the account
    EMAIL_ACCOUNT = ""
    #Set password of the account
    EMAIL_PASSWORD = ""
    main(EMAIL_ACCOUNT,EMAIL_PASSWORD)
