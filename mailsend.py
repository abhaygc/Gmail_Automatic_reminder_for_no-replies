import os
import smtplib
import email
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
import sys
from email.mime.text import MIMEText
import pymongo
import datetime
import time

#This function creates DB if not already in place
def dbcreate():
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
    return email_sent

def main(sender,gmail_password,recipients,subject,body,is_reminder,resub,reminder_mails,reminder_numbers,remsg,remsms,remdatetime,timestamp,attachments):

    data=[] #To build reminder dictionary for each email recipient

    for i in recipients:
        d={'id':i,'resub':resub,'remsg':remsg,'remmails':reminder_mails,'remnumbers':reminder_numbers,
           'remsms':remsms,'remdatetime':remdatetime,'timestamp':timestamp}
        data.append(d)

    #Checking whether DB present or not. If not create it.
    email_sent = dbcreate()

    #Generating a MesaageID locally so that we can store it and use it in future to track replies
    #Most of the current day email systems add 'In-Reply' parameter to header of reply email
    #'In-Reply' consists of MessageID of original mail for which reply mail is sent
    msgid=email.utils.make_msgid()

    #Our email can contain attachments too so creating MIMEMultipart() object
    outer = MIMEMultipart()

    #User add_header() method to add header values

    outer.add_header('Subject',subject) #Adding subject to header
    outer.add_header('From',sender) #Adding from to header
    outer.add_header('Message-ID',msgid) #Adding msgid to header

    #If you want to send customised emails rather than plain text then HTML programmed mails must be used
    #The recieving email system will parse the email as HTML lines. So you could use HTML tags like <b></b> to make text bold,etc.
    #Here we are attaching the Text part to our Multipart object
    outer.attach(MIMEText(body, "html"))

    #Attaching attachments to Multipart object
    for file in attachments:
        try:
            with open(file, 'rb') as fp:
                #Since attachment is not restricted to any file type
                #We are using Main Content type: application and Sub Content type: octet-stream for the part
                msg = MIMEBase('application', "octet-stream")

                #Ataaching the attachment file to the part
                msg.set_payload(fp.read())
            #Files must be transferred in ASCII coding so the attachment is encoded using base scheme
            encoders.encode_base64(msg)

            # 'Content-Disposition' can have two values viz.
            # 1. 'inline' :  This tells the email reader to open the file within the email as part of web page
            # 2. 'attachment': This tells the email reader to download the file locally and that to when user clicks on it
            msg.add_header('Content-Disposition', 'attachment', filename=os.path.basename(file))

            #Here we are attaching the attachment part to our Multipart object
            outer.attach(msg)
        except:
            print("Unable to open one of the attachments. Error: ", sys.exc_info()[0])
            raise


    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as s:
            #ehlo() method identifies our system with Email Server
            s.ehlo()

            #starttls() shifts our connection to TLS mode for secure connection
            s.starttls()

            #As per smtplib documentation we need to again identify our system after using starttls
            s.ehlo()

            #login() method to login to the account
            s.login(sender, gmail_password)

            #Adding 'BCC' header doesn't work
            #So we loop over receipents and sendmail to each individual
            for recipient in recipients:

                #Adding 'To' header
                outer.add_header('To',recipient)

                #Converting our whole mail to a single string to send mail
                composed = outer.as_string()

                #Using sendmail() method to send mail
                #Arguments paased are sender(i.e. From) , recipient(i.e. To) , composed(i.e. The mail contents)
                s.sendmail(sender, recipient, composed)

                #We need to just delete current 'To' header so that we could reuse the smae Mulitpart mail object for other recipients
                outer.__delitem__('To')

            #Close smtp connection
            s.close()
        print("Email sent!")

        #Insering the data into Database
        email_sent.insert_one(
            {
                'to':recipients,
                'from':sender,
                'subject':outer['Subject'],
                'MessageID':msgid,
                'DateTime':datetime.datetime.now(),
                'time':time.time(),
                'attachments':attachments,
                'message':body,
                'reminder':data,
                'reminder_mails':reminder_mails,
                'reminder_numbers':reminder_numbers,
                'is_reminder':is_reminder
            }
        )

    except:
        print("Unable to send the email. Error: ", sys.exc_info()[0])

        raise   #raise keyword without exception mentioned reraises the last exception so you know what went wrong



if __name__ == '__main__':
    #This is to test manually

    #You can set the arguments mentioned below dynamically via code and directly pass them to main()
    #Just get through the data types of the arguments

    #Mention senders gmail email id in string variable below
    sender = ""

    #Set your gmail password in below variable
    gmail_password = ""

    #Mention email ids of recipients here in the list below
    #For e.g ; recipients = ['gmail@gmail.com','yahoo@yahho.com']
    recipients =[]

    #Assign your subject to below string
    subject='Programmed Email'

    #Write your email body here; It can be in HTML too;
    body='<b><u>This cool html mail</u></b>'

    #is_reminder is to differentiate the basic mails and reminder mails sent through our systems
    #0 means its basic email; 1 means its reminder email;
    #Emails sent through our system as reminder would have below variable equal to 1
    #flag that email being sent is not a reminder
    is_reminder=0

    #Mention email ids of recipients to whom reminder must be sent in the list below
    #For e.g ; reminder_mails = ['gmail@gmail.com','yahoo@yahho.com']
    reminder_mails = []

    #Mention phone numbers of recipients to whom reminder must be sent in the list below
    #remember values must be integer
    #For e.g ; reminder_mails = [1233456789,11111122235]
    reminder_numbers=[]

    #Assign your Reminder mail subject
    resub=' Reminder email '

    #Assign content for reminder mail and message
    remsg=' Reminder for no reply '

    #remsms is used to flag whther to send the SMS reminder or not for a mail;
    # 0 = No & 1 = Yes
    remsms=0

    #Reminder deadline Datetime; This would be used in case you want to display date time of reminder
    #For eg to assign current date itself for deadline use;
    # remdate=datetime.datetime.now().date()
    remdatetime=datetime.datetime.now()


    #timestamp variable below is used to store reminder deadline timestamp in milliseconds;
    # This would be used to check whether the deadline is passed or not
    timestamp = datetime.datetime.now().timestamp()*1000

    #Append the path of files to be attached in below list
    #For eg; attachments = ['C:/Downloads/sample.pdf','C:/Desktop/sample.jpg']
    #Keep it empty in no strings
    attachments = []
    main(sender,gmail_password,recipients,subject,body,is_reminder,resub,reminder_mails,reminder_numbers,remsg,remsms,remdatetime,timestamp,attachments)
    
    
