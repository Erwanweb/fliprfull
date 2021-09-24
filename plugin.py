#           flipr Plugin
#
#           Authors:
#                       Copyright (C) 2020 yoyey
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
"""
<plugin key="fliprfull" name="Fliprfull" author="yoyey" version="1.0.0" externallink="https://github.com/Erwanweb/fliprfull">
    <params>
        <param field="Username" label="Adresse e-mail" width="200px" required="true" default=""/>
        <param field="Password" label="Mot de passe" width="200px" required="true" default="" password="true"/>
        <param field="Mode1" label="Numero de serie du flipr" required="true" default=""/>
        <param field="Mode3" label="Debug" width="75px">
            <options>
                <option label="Non" value="0"  default="true" />
                <option label="Oui" value="1"/>
                <option label="Avancé" value="2"/>
            </options>
        </param>
    </params>
</plugin>
"""

# https://www.domoticz.com/wiki/Developing_a_Python_plugin

import Domoticz
import sys
from base64 import b64encode
import json
from urllib.parse import quote
import re
from datetime import datetime
from datetime import timedelta
from time import strptime
from datetime import time
import html
import requests
import os

baseUrl = "https://apis.goflipr.com"
oauth2data = {'grant_type':'password', 'password':'', 'username':''}
oauth2Url = baseUrl + "/OAuth2/token"
headerData = { 'Content-Type':'application/json', 'Authorization':''}

devicesdef = [{'index':1, 'name':'Temperature', 'description':'Capteur de temperature', 'type':80, 'subType':5 },
              {'index':2, 'name':'Batterie', 'description':'niveau de batterie du capteur', 'type':243, 'subType':6},
              {'index':3, 'name':'Desinfectant', 'description':'Désinfectant', 'type':249, 'subType':19, 'image':'xfr_chlore.zip'},
              {'index':4, 'name':'PH', 'description':'Ph', 'type':234, 'subType':31, 'image':'xfr_ph.zip'},
              {'index':5, 'name':'Redox', 'description':'Redox', 'type':234, 'subType':31, 'image':'xfr_ph.zip'},
              {'index':6, 'name':'Conductivite', 'description':'Conductivite', 'type':234, 'subType':31, 'image':'xfr_ph.zip'}]
class BasePlugin:
    calculatePeriod = 30 # refresh time in minute
    nextRefresh = datetime.now()
    # boolean: to check that we are started, to prevent error messages when disabling or restarting the plugin
    isStarted = None
    # object: http connection
    httpConn = None
    # string: name of the Flipr device
    sDeviceName = "Flipr"
    sDeviceNameTemp = "Flipr Temp"
    # string: description of the Flipr device
    sDescription = "analyseur d'eau"
    sDescriptionTemp = "analyseur d'eau temp"
    # string: step name of the state machine
    sConnectionStep = None
    # string: username for flipr website
    sUser = None
    # string: password for flipr website
    sPassword = None
    # string : serial number of the fliper device
    sSerial = None
    iDebugLevel = None
    #store the token
    token = None
    lastDateTime= None
    #get phImage
    phImage = None
    def __init__(self):
        self.isStarted = False
        self.httpConn = None
        self.sConnectionStep = "idle"
        self.bHasAFail = False

    def myDebug(self, message):
        if self.iDebugLevel:
            Domoticz.Log(message)


    # getToken : get the bearer type token
    def getToken(self):
        oauth2data['password'] = self.sPassword
        oauth2data['username'] = self.sUser
        response = requests.post(oauth2Url, data = oauth2data)
        #print the response text (the content of the requested file):
        jsontoken = response.json()
        return jsontoken['access_token']
    # getData : get the historical data
    def getData(self):
        urlData = baseUrl + '/modules/' + self.sSerial + '/survey/Last'
        headerData['Authorization'] = 'Bearer ' + self.token
        x = requests.get(url = urlData, headers = headerData, verify=False)
        return x.json()

    # Create Domoticz device
    def createDevice(self):

        # Only if not already done
        for device in devicesdef:
            if not device['index'] in Devices:
              # Images
              # Check if images are in database
              image = 0
              Domoticz.Debug("Filename: " + str(device))
              Domoticz.Debug(str(Images))
              if 'image' in device:
                zipName = device['image']
                fileName = os.path.splitext(zipName)[0]
                if fileName not in Images:

                  Domoticz.Debug("Filename:" + str(fileName))
                  Domoticz.Image(zipName).Create()
                  try:
                    Domoticz.Debug("Images[fileName].ID:" + str(Images[fileName].ID))
                    image = Images[fileName].ID
                  except:
                    image = 0
                Domoticz.Debug("Image created. ID: "+str(image) + "Filename:" + str(fileName))
              Domoticz.Device(Name=device['name'],  Unit=device['index'], Type=device['type'], Subtype=device['subType'], Description=device['description'], Image=image, Used=1).Create()
            if not (device['index'] in Devices):
                Domoticz.Error("Ne peut ajouter Flipr à la base de données. Vérifiez dans les paramètres de Domoticz que l'ajout de nouveaux dispositifs est autorisé")
                return False
        return True

    def createAndAddToDevice(self, index, sVal, typeVal, subTypeVal):
        if not self.createDevice():
            return False
        # -1.0 for counter
        self.myDebug("Mets dans la BDD la valeur " + sVal)
        self.myDebug("images : " + str(Images) )
        Devices[index].Update(nValue=-1, sValue=sVal, Type=typeVal, Subtype=subTypeVal, Image=102)
        return True

    # Update value shown on Domoticz dashboard
    def updateDevice(self, usage):
        Domoticz.log("update Device");
        if not self.createDevice():
            return False

    # Show error in state machine context
    def showStepError(self, hours, logMessage):
        if hours:
            Domoticz.Error(logMessage + " durant l'étape " + self.sConnectionStep)
        else:
            Domoticz.Error(logMessage + " durant l'étape " + self.sConnectionStep)


    # Handle the connection state machine
    def handleConnection(self, Data = None):
        self.token = self.getToken()
        jsonData = self.getData()
        if self.lastDateTime != jsonData['DateTime']:
            Domoticz.Debug("Enregistrement des donnees" + str(jsonData) + " "+ str(jsonData['DateTime']))
            dateTime = datetime.strptime(jsonData['DateTime'],"%Y-%m-%dT%H:%M:%SZ")
            tempVal = str(jsonData['Temperature'])
            self.createAndAddToDevice(1, tempVal, 80, 5)
            PHVal = str(jsonData['PH']['Value'])
            self.createAndAddToDevice(4, PHVal, 243, 31)
            RedoxVal = str(jsonData['OxydoReductionPotentiel']['Value'])
            self.createAndAddToDevice(5, RedoxVal, 243, 31)
            ConductivityVal = str(jsonData['Conductivity']['Value'])
            self.createAndAddToDevice(6, ConductivityVal, 243, 31)
            batVal = str(jsonData['Battery']['Deviation'] * 100)
            self.createAndAddToDevice(2, batVal, 243,6)
            chloreText = str(jsonData['Desinfectant']['Message'])
            self.createAndAddToDevice(3, chloreText, 243,19)
        self.lastDateTime = jsonData['DateTime']

    def dumpDictToLog(self, dictToLog):
        if self.iDebugLevel:
            if isinstance(dictToLog, dict):
                self.myDebug("Dict details ("+str(len(dictToLog))+"):")
                for x in dictToLog:
                    if isinstance(dictToLog[x], dict):
                        self.myDebug("--->'"+x+" ("+str(len(dictToLog[x]))+"):")
                        for y in dictToLog[x]:
                            if isinstance(dictToLog[x][y], dict):
                                for z in dictToLog[x][y]:
                                    self.myDebug("----------->'" + z + "':'" + str(dictToLog[x][y][z]) + "'")
                            else:
                                self.myDebug("------->'" + y + "':'" + str(dictToLog[x][y]) + "'")
                    else:
                        self.myDebug("--->'" + x + "':'" + str(dictToLog[x]) + "'")
            else:
                self.myDebug("Received no dict: " + str(dictToLog))

    def onStart(self):
        self.myDebug("onStart called")

        Domoticz.Log("plugin pour la recuperation de la derniere donnee du flipr")

        self.sUser = Parameters["Username"]
        self.sPassword = Parameters["Password"]
        self.sSerial = Parameters["Mode1"]
        try:
            self.iDebugLevel = int(Parameters["Mode3"])
        except ValueError:
            self.iDebugLevel = 0

        if self.iDebugLevel >= 1:
            Domoticz.Debugging(1)

        Domoticz.Log("Adresse e-mail mise à " + self.sUser)
        if self.sPassword:
            Domoticz.Log("Mot de passe entré")
        else:
            Domoticz.Log("Mot de passe laissé vide")
        if self.sSerial:
            Domoticz.Log("Numero de serie reneigne")
        else:
            Domoticz.Log("Numero de serie laisse vide")
        Domoticz.Log("Debug mis à " + str(self.iDebugLevel))

        # most init
        self.__init__()


        if self.createDevice():
            self.nextRefresh = datetime.now()

        # Now we can enabling the plugin
        self.isStarted = True

    def onStop(self):
        Domoticz.Debug("onStop called")
        # prevent error messages during disabling plugin
        self.isStarted = False

    def onConnect(self, Connection, Status, Description):
        Domoticz.Debug("onConnect called")
        if self.isStarted and (Connection == self.httpConn):
            self.handleConnection()

    def onMessage(self, Connection, Data):
        Domoticz.Debug("onMessage called")

        # if started and not stopping
        if self.isStarted and (Connection == self.httpConn):
            self.handleConnection(Data)

    def onDisconnect(self, Connection):
        Domoticz.Debug("onDisconnect called")

    def onHeartbeat(self):
        Domoticz.Debug("onHeartbeat() called")
        now = datetime.now()

        if self.nextRefresh <= now:
            self.nextRefresh = now + timedelta(minutes=self.calculatePeriod)
            self.handleConnection()

global _plugin
_plugin = BasePlugin()

def onStart():
    global _plugin
    _plugin.onStart()

def onStop():
    global _plugin
    _plugin.onStop()

def onConnect(Connection, Status, Description):
    global _plugin
    _plugin.onConnect(Connection, Status, Description)

def onMessage(Connection, Data):
    global _plugin
    _plugin.onMessage(Connection, Data)

def onCommand(Unit, Command, Level, Hue):
    global _plugin
    _plugin.onCommand(Unit, Command, Level, Hue)

def onDeviceAdded(Unit):
    global _plugin

def onDeviceModified(Unit):
    global _plugin

def onDeviceRemoved(Unit):
    global _plugin

def onNotification(Name, Subject, Text, Status, Priority, Sound, ImageFile):
    global _plugin
    _plugin.onNotification(Name, Subject, Text, Status, Priority, Sound, ImageFile)

def onDisconnect(Connection):
    global _plugin
    _plugin.onDisconnect(Connection)

def onHeartbeat():
    global _plugin
    _plugin.onHeartbeat()

# Generic helper functions
def dictToQuotedString(dParams):
    result = ""
    for sKey, sValue in dParams.items():
        if result:
            result += "&"
        result += sKey + "=" + quote(str(sValue))
    return result

def DumpConfigToLog():
    for x in Parameters:
        if Parameters[x] != "":
            self.myDebug( "'" + x + "':'" + str(Parameters[x]) + "'")
    self.myDebug("Device count: " + str(len(Devices)))
    for x in Devices:
        self.myDebug("Device:           " + str(x) + " - " + str(Devices[x]))
        self.myDebug("Device ID:       '" + str(Devices[x].ID) + "'")
        self.myDebug("Device Name:     '" + Devices[x].Name + "'")
        self.myDebug("Device iValue:    " + str(Devices[x].iValue))
        self.myDebug("Device sValue:   '" + Devices[x].sValue + "'")
        self.myDebug("Device LastLevel: " + str(Devices[x].LastLevel))
    return
