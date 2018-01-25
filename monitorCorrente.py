#!/usr/bin/python
# -*- coding: utf-8 -*-

import serial
import argparse
import logging
import sqlite3
import smtplib
import ConfigParser
from bs4 import BeautifulSoup
from time import strftime, mktime
from datetime import datetime
from email.MIMEMultipart import MIMEMultipart
from email.MIMEText import MIMEText

parser = argparse.ArgumentParser(description='Controlla la presenza della corrente elettrica e segnala eventuali disservizi prolungati.')
parser.add_argument('--verbose', '-V', dest='verbose', action='store_true',
                   help='Visualizza a video i valori letti e i messaggi')

args = parser.parse_args()

inifile = ConfigParser.RawConfigParser()
inifile.read('monitorCorrente.ini')

FORMAT = '%(message)s'

if args.verbose:
    logging.basicConfig(level=logging.INFO,format=FORMAT)
    #print('Parametro verbose specificato')
else:
    logging.basicConfig(level=logging.ERROR,format=FORMAT)

def sendMail(to, subject, body ):
   "Invia una email con i parametri in ingresso usando gmail"

   gmail_user = 'nx01.home@gmail.com'
   gmail_password = 'Nx01h0m3'

   sent_from = 'Monitor corrente casa CS'

   msg = MIMEMultipart()
   msg['From'] = sent_from
   msg['To'] = ', '.join(to) 
   msg['Subject'] = subject

   msg.attach(MIMEText(body, 'plain'))

   try:
       server = smtplib.SMTP('smtp.gmail.com', 587)
       server.starttls()
       server.login(gmail_user, gmail_password)
       text = msg.as_string()
       server.sendmail(sent_from, to, text)
       server.quit()
       logging.info('Email sent!')
   except Exception as e1:
       logging.info('Errere in invio mail: ' + str(e1))
   return;

ser = serial.Serial(
    port='/dev/ttyUSB0',\
    baudrate=57600,\
    parity=serial.PARITY_NONE,\
    stopbits=serial.STOPBITS_ONE,\
    bytesize=serial.EIGHTBITS,\
        timeout=0)

#dbPath = '/home/remigio/Script/monitorCorrente/monitorCorrente.db'
dbPath = inifile.get('DATABASE','dbFile')
logging.info("DB File = " + dbPath)
conn = sqlite3.connect(dbPath)
cursor = conn.cursor()

logging.info("Connected to: " + ser.portstr)

line = ""

#sendMail(['remigio.armano@gmail.com', 'letiziatoscano70@gmail.com'], 'Prova mail Python', 'Ciao,\n\nquesta è una email inviata da Python.\n\n\nSaluti' )

end=False
while not end:
   try:
      for c in ser.read():
          line+=c
          if c == '\n':
              logging.info("Line: " + line)
	      if line.find('</msg>') == -1:
	          continue
              try:
                  soup=BeautifulSoup(line,'lxml')
                  watts = int(soup.find('watts').get_text())
                  temp = float(soup.find('tmpr').get_text())
              except Exception as e1:
                  logging.info("Error in xml parsing:" + str(e1))
                  end = True
                  break
              orario = datetime.now()
              logging.info("Time = " + strftime("%d.%m.%Y %H:%M:%S", orario.timetuple()))
              logging.info("Watts = " + str(watts))
              logging.info("Temp = " + str(temp))
              try:
                  cursor.execute("select valore from parametri where parametro='Ultima lettura'")
                  ultimaLettura = int(cursor.fetchone()[0])
                  logging.info("Ultima lettura = " + str(ultimaLettura))
                  cursor.execute("select valore from parametri where parametro='Orario ultima lettura'")
                  orarioUltimaLettura = datetime.strptime(cursor.fetchone()[0], "%d.%m.%Y %H:%M:%S")
                  logging.info("Orario Ultima lettura = " + str(orarioUltimaLettura))
                  gapMisure = int((mktime(orario.timetuple()) - mktime(orarioUltimaLettura.timetuple())) / 60)
                  logging.info("Minuti da ultima misura = " + str(gapMisure))
		  if ultimaLettura == 0:
		  	if watts == 0:
			  	sendMail(['remigio.armano@gmail.com'], 'ATTENZIONE: assenza corrente', 'Monitor corrente ha rilevato l''assenza di corrente da ' + str(gapMisure) + ' minuti. \nA breve verrà effettuato lo shutdown dei sistemi Home')
			else:
			  	sendMail(['remigio.armano@gmail.com'], 'ATTENZIONE: corrente ripristinata', 'Monitor corrente ha rilevato il ripristino della linea elettrica.\n\nI sistemi non sono stati spenti')
		  cursor.execute("update parametri set valore = ? where parametro='Ultima lettura'", [str(watts)])
		  cursor.execute("update parametri set valore = ? where parametro='Orario ultima lettura'", [strftime("%d.%m.%Y %H:%M:%S", orario.timetuple())])
		  conn.commit()
              except Exception as e2:
                  logging.info("Error in SQLite block: " + str(e2))
              end = True
              line = ""
   except serial.serialutil.SerialException:
      pass

ser.close()
cursor.close()
conn.close()
