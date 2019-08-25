import mailread

import smtplib
import email

from email.mime.multipart import MIMEMultipart
import sys
from email.mime.text import MIMEText
import pymongo
import datetime
import time

#Remember to import your sms script in case you want to send sms reminders

#isPause used to check control consecutive reminder calls
isPause = False


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

def main(sender,gmail_password,recipients,subject,body,is_reminder):
    email_sent = dbcreate()

    msgID= email.utils.make_msgid()

    outer = MIMEMultipart()
    outer.add_header('Subject',subject)
    outer.add_header('From',sender)

    outer.add_header('Message-ID',msgID)

    # Send the email
    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as s:
            s.ehlo()
            s.starttls()
            s.ehlo()
            s.login(sender, gmail_password)
            for recipient in recipients:
                outer.add_header('To',recipient)
                outer.attach(MIMEText(body, "html"))
                composed = outer.as_string()

                s.sendmail(sender, recipient, composed)
                outer.__delitem__('To')

            s.close()

        print("Reminder mail sent!")

        email_sent.insert_one(
            {
                'to':recipients,
                'from':sender,
                'subject':outer['Subject'],
                'MessageID':str(outer['Message-ID']),
                'DateTime':datetime.datetime.now(),
                'time':time.time(),
                'message':body,
                'is_reminder':is_reminder
            }
        )

    except:
        print("Unable to send the email. Error: ", sys.exc_info()[0])
        raise


def reminder(EMAIL_ACCOUNT,EMAIL_PASSWORD):
    global isPause
    #Check if previous reminder() calls are still running using isPause

    if(isPause != True):
        #Turn isPause True so that next reminder() call doesn't collapse with current call
        isPause = True

        #Get list of emails not replied to emails sent through our systems
        no_replies_dict=mailread.main(EMAIL_ACCOUNT,EMAIL_PASSWORD)

        for i in no_replies_dict:
            #Getting parameters like remider deadline , reminder message subject and content
            #Emails and Phone numbers on which reminder needs to be sent
            reminder = i['resub']
            body=i['remsg']
            re= i['timestamp']
            reminder_mails = i['remmails']
            reminder_numbers=i['remnumbers']

            #Getting current time so that we could check if deadline has crossed or not
            currtime = datetime.datetime.now()
            currtime = currtime.timestamp()*1000

            if(currtime>re):
                #Deadline has crossed
                #We call main() to send the reminder
                #This is same as main() in mailsend.py just with less paramters
                main('foodwastagemanger@gmail.com',EMAIL_PASSWORD,reminder_mails,reminder,body,1)

                #Check if SMS reminder was enabled for the mail
                if i['remsms']==1:
                    #Reminder was enabled
                    print(" SMS reminder was enabled . ")
                    #call your sms method from here

        #Turn isPause False so next reminder() calls can execute
        isPause = False


#Infinite loop to keep checking whether replies have arrived or not
#and to check reminder deadline
while(True):

    #Set email id of the account
    EMAIL_ACCOUNT = ""
    #Set password of the account
    EMAIL_PASSWORD = ""

    #Call reminder() to check for reminder
    reminder(EMAIL_ACCOUNT,EMAIL_PASSWORD)

    #Sleep for 10 seconds
    time.sleep(10)

