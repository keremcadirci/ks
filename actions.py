from typing import Any, Text, Dict, List, Union, Optional
from rasa_sdk.events import SlotSet, Form
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.forms import FormAction

from urllib.request import urlopen
from xml.etree.ElementTree import parse
from xml.etree import ElementTree

import datetime
import requests
import json
import os
import pandas as pd
import xml.etree.ElementTree as ET

API_ENDPOINT = "http://localhost:28080/services/chatbotcore/chat/change-conversation-target/{sender_id}/GENESYS"

def stripNs(el):
    '''Recursively search this element tree, removing namespaces.'''
    if el.tag.startswith("{"):
        el.tag = el.tag.split('}', 1)[1]  # strip namespace
    for k in el.attrib.keys():
        if k.startswith("{"):
            k2 = k.split('}', 1)[1]
            el.attrib[k2] = el.attrib[k]
            del el.attrib[k]
    for child in el:
        stripNs(child)

def capitalize(location):
    if location[0] == 'ç':
        location = location[1:]
        location = 'Ç' + location
    elif location[0] == 'ı':
        location = location[1:]
        location = 'I' + location
    elif location[0] == 'i':
        location = location[1:]
        location = 'İ' + location
    elif location[0] == 'ş':
        location = location[1:]
        location = 'Ş' + location
    else:
        location = location.capitalize()
    return location

def get_currency():

    tree = ET.parse('.\\GetCurrencyExchangeRates.xml')
    root = tree.getroot()

    # define namespace mappings to use as shorthand below
    namespaces = {
        'xmlns':'http://tempuri.org/',
    }

    # reference the namespace mappings here by `<name>:`

    fxRateDataContractCompareds = root.findall(
        './xmlns:Value'
        '/xmlns:FXRateContractCompared',
        namespaces,
    )

    fxRateDataContracts = root.findall(
        './xmlns:Value'
        '/xmlns:FXRateContractCompared'
        '/xmlns:FXRateDataContract',
        namespaces,
    )

    exchangeRates = {}
    i = 0

    for fxRateDataContractCompared in fxRateDataContractCompareds:
        stripNs(fxRateDataContractCompared)
        dataTable = {}
    
        currencyBidIncreaseValue = fxRateDataContractCompared.find("CurrencyBidIncreaseValue").text if fxRateDataContractCompared.find("CurrencyBidIncreaseValue") is not None else None
        
        currencyBidIncreaseValue = float(currencyBidIncreaseValue)
        currencyBidIncreaseValue = "{:,.2f}".format(currencyBidIncreaseValue)
        currencyBidIncreaseValue = str(currencyBidIncreaseValue).replace(".",",")
        dataTable['currencyBidIncreaseValue'] = currencyBidIncreaseValue
    
        shortCode = fxRateDataContracts[i].find("CurrencyShortCode").text if fxRateDataContracts[i].find("CurrencyShortCode") is not None else None
        shortName = fxRateDataContracts[i].find("CurrencyShortCode").text if fxRateDataContracts[i].find("CurrencyShortCode") is not None else None
        currencyName = fxRateDataContracts[i].find("CurrencyDescription").text if fxRateDataContracts[i].find("CurrencyDescription") is not None else None
        fec = fxRateDataContracts[i].find("Fec").text if fxRateDataContracts[i].find("Fec") is not None else None
        buyRate = fxRateDataContracts[i].find("CurrencyBid").text if fxRateDataContracts[i].find("CurrencyBid") is not None else None
        sellRate = fxRateDataContracts[i].find("CurrencyAsk").text if fxRateDataContracts[i].find("CurrencyAsk") is not None else None
        
        buyRate = float(buyRate)
        buyRate = "{:,.4f}".format(buyRate)
        buyRate = str(buyRate).replace(".",",")

        dataTable['shortName'] = shortName
        dataTable['currencyName'] = currencyName
        dataTable['buyRate'] = buyRate
        dataTable['sellRate'] = sellRate
        dataTable['fec'] = fec
        dataTable['parity'] = currencyBidIncreaseValue
    
        if "ALT" in shortCode:
            shortCode = "ALT"
        elif "GMS" in shortCode:
            shortCode = "GMS"
        elif "PLT" in shortCode:
            shortCode = "PLT"
        elif "ZCeyrek" in shortCode:
            shortCode = "Ceyrek"
    
        exchangeRates[shortCode] = dataTable
        i = i+1

    return exchangeRates

def find_branch(sehir, semt):

    tree = ET.parse('.\\Location.xml')
    root = tree.getroot()

    namespaces = {
        'soap': 'http://www.w3.org/2003/05/soap-envelope',
        'xmlns': 'http://tempuri.org/',
    }

    branchList = root.findall(
        './soap:Body'
        '/xmlns:GetBranchCoordinateListResponse'
        '/xmlns:GetBranchCoordinateListResult'
        '/xmlns:Value'
        '/xmlns:BranchList'
        '/xmlns:WorkGroupContract',
        namespaces,
    )

    branches = {}
    selectedCityName = None

    for branch in branchList:
        stripNs(branch)
        name = branch.find("Name").text if branch.find("Name") is not None else None
        cityName = branch.find("CityName").text if branch.find("CityName") is not None else None
        branchId = branch.find("BranchId").text if branch.find("BranchId") is not None else None
        branchName = branch.find("BranchName").text if branch.find("BranchName") is not None else None
        longitude = branch.find("Longitude").text if branch.find("Longitude") is not None else None
        latitude = branch.find("Latitude").text if branch.find("Latitude") is not None else None
        address = branch.find("Address").text if branch.find("Address") is not None else None
        phone = branch.find("Phone").text if branch.find("Phone") is not None else None
        fax = branch.find("Fax").text if branch.find("Fax") is not None else None
        countryName = branch.find("CountryName").text if branch.find("CountryName") is not None else None

        dataTable = {}
        dataTable["name"] = name
        dataTable["cityName"] = cityName
        dataTable["branchId"] = branchId
        dataTable["branchName"] = branchName
        dataTable["longitude"] = longitude
        dataTable["latitude"] = latitude
        dataTable["address"] = address
        dataTable["phone"] = phone
        dataTable["fax"] = fax
        dataTable["countryName"] = countryName
                
        if cityName in branches:
            branches[cityName].append(dataTable)
        else:
            branches[cityName] = [dataTable]
            
        if sehir is not None:
            sehir = capitalize(sehir)
            if sehir == dataTable['cityName']:
                selectedCityName = dataTable['cityName']
            else:
                if selectedCityName is None and sehir in dataTable['branchName']:
                    selectedCityName = dataTable['cityName']
                else:
                    if selectedCityName is None and sehir in dataTable['address']:
                        selectedCityName = dataTable['cityName']
            
        if sehir is None and semt is not None:
            if "i" in semt:
                semtConvert = semt.replace("i", "İ")
                semtUpper = semtConvert.upper()
            else: 
                semtUpper = semt.upper()

            if semtUpper == dataTable['countryName']:
                selectedCityName = dataTable['cityName']
            else:
                semtCapitalize = capitalize(semt)
                if selectedCityName is None and semtCapitalize in dataTable['branchName']:
                    selectedCityName = dataTable['cityName']
                else:
                    if selectedCityName is None and semtCapitalize in dataTable['address']:
                        selectedCityName = dataTable['cityName']
                
    if sehir is not None:
        if selectedCityName is not None:
            selectedCity = pd.DataFrame.from_dict(branches[selectedCityName])
            selected = selectedCity
            if selected.empty:
                selected = selectedCity[selectedCity['branchName'].str.contains(sehir) | selectedCity['branchName'].str.contains(sehir[1:])]
            if selected.empty:
                selected = selectedCity[selectedCity['address'].str.contains(sehir) | selectedCity['address'].str.contains(sehir[1:])]

            if semt is not None:
                semt = capitalize(semt)
                selected = selectedCity[selectedCity['address'].str.contains(semt) | selectedCity['address'].str.contains(semt[1:])]
                if selected.empty:
                    selected = selectedCity
        else:
            notFoundResponse = json.loads('{"response":"error"}')
            return notFoundResponse

    else:
        if selectedCityName is not None:
            semt = capitalize(semt)
            selectedCity = pd.DataFrame.from_dict(branches[selectedCityName])
            selected = selectedCity[selectedCity['branchName'].str.contains(semt) | selectedCity['branchName'].str.contains(semt[1:])]
            if selected.empty:
                selected = selectedCity[selectedCity['address'].str.contains(semt) | selectedCity['address'].str.contains(semt[1:])]
            if selected.empty:
                selected = selectedCity
        else:
            notFoundResponse = json.loads('{"response":"error"}')
            return notFoundResponse

    answerList = []

    for index, row in selected.iterrows():
        dataTable = {}
        # name = row['name'].split()
        # newName = row['name'].rsplit(' ', 1)[0]
        # i = 0
        # for element in name:
        #     locationType = name[i]
        #     i = i + 1
        # dataTable['name'] = newName
        dataTable['name'] = row['name']
        dataTable['city'] = row['cityName']
        dataTable['town'] = row['countryName']
        dataTable['address'] = row['address']
        dataTable['branchId'] = row['branchId']
        dataTable['phone'] = row['phone']
        dataTable['fax'] = row['fax']
        dataTable['lat'] = row['latitude']
        dataTable['long'] = row['longitude']
        answerList.append(dataTable)

    answer = {}
    answer["type"] = "maps"
    answer["response"] = "success"
    answer["location_type"] = "Şube"
    answer["img"] = "/content/img/sube.png"
    answer["arr"] = answerList

    return answer

def find_atm(sehir, semt):

    tree = ET.parse('.\\Location.xml')
    root = tree.getroot()

    namespaces = {
        'soap': 'http://www.w3.org/2003/05/soap-envelope',
        'a': 'http://tempuri.org/',
    }

    atmData = root.findall(
        './soap:Body'
        '/a:GetBranchCoordinateListResponse'
        '/a:GetBranchCoordinateListResult'
        '/a:Value'
        '/a:ATMList'
        '/a:WorkGroupContract',
        namespaces,
    )

    atmList = {}
    selectedCityName = None

    for atm in atmData:
        stripNs(atm)
        name = atm.find("Name").text if atm.find("Name") is not None else None
        cityName = atm.find("CityName").text if atm.find("CityName") is not None else None
        branchId = atm.find("BranchId").text if atm.find("BranchId") is not None else None
        branchName = atm.find("BranchName").text if atm.find("BranchName") is not None else None
        longitude = atm.find("Longitude").text if atm.find("Longitude") is not None else None
        latitude = atm.find("Latitude").text if atm.find("Latitude") is not None else None
        address = atm.find("Address").text if atm.find("Address") is not None else None
        phone = atm.find("Phone").text if atm.find("Phone") is not None else None
        fax = atm.find("Fax").text if atm.find("Fax") is not None else None
        countryName = atm.find("CountryName").text if atm.find("CountryName") is not None else None
        
        dataTable = {}
        dataTable["name"] = name
        dataTable["cityName"] = cityName
        dataTable["branchId"] = branchId
        dataTable["branchName"] = branchName
        dataTable["longitude"] = longitude
        dataTable["latitude"] = latitude
        dataTable["address"] = address
        dataTable["phone"] = phone
        dataTable["fax"] = fax
        dataTable["countryName"] = countryName

        if cityName in atmList:
            atmList[cityName].append(dataTable)
        else:
            atmList[cityName] = [dataTable]

        if sehir is not None:
            sehir = capitalize(sehir)
            if sehir == dataTable['cityName']:
                selectedCityName = dataTable['cityName']
            else:
                if selectedCityName is None and sehir in dataTable['branchName']:
                    selectedCityName = dataTable['cityName']
                else:
                    if selectedCityName is None and sehir in dataTable['address']:
                        selectedCityName = dataTable['cityName']

        if sehir is None and semt is not None:
            if "i" in semt:
                semtConvert = semt.replace("i", "İ")
                semtUpper = semtConvert.upper()
            else: 
                semtUpper = semt.upper()

            if semtUpper == dataTable['countryName']:
                selectedCityName = dataTable['cityName']
            else:
                semtCapitalize = capitalize(semt)
                if selectedCityName is None and semtCapitalize in dataTable['branchName']:
                    selectedCityName = dataTable['cityName']
                else:
                    if selectedCityName is None and semtCapitalize in dataTable['address']:
                        selectedCityName = dataTable['cityName']
                
    if sehir is not None:
        if selectedCityName is not None:
            selectedCity = pd.DataFrame.from_dict(atmList[selectedCityName])
            selected = selectedCity
            if selected.empty:
                selected = selectedCity[selectedCity['branchName'].str.contains(sehir) | selectedCity['branchName'].str.contains(sehir[1:])]
            if selected.empty:
                selected = selectedCity[selectedCity['address'].str.contains(sehir) | selectedCity['address'].str.contains(sehir[1:])]

            if semt is not None:
                semt = capitalize(semt)
                selected = selectedCity[selectedCity['address'].str.contains(semt) | selectedCity['address'].str.contains(semt[1:])]
                if selected.empty:
                    selected = selectedCity
        else:
            notFoundResponse = json.loads('{"response":"error"}')
            return notFoundResponse

    else:
        if selectedCityName is not None:
            semt = capitalize(semt)
            selectedCity = pd.DataFrame.from_dict(atmList[selectedCityName])
            selected = selectedCity[selectedCity['branchName'].str.contains(semt) | selectedCity['branchName'].str.contains(semt[1:])]
            if selected.empty:
                selected = selectedCity[selectedCity['address'].str.contains(semt) | selectedCity['address'].str.contains(semt[1:])]
            if selected.empty:
                selected = selectedCity
        else:
            notFoundResponse = json.loads('{"response":"error"}')
            return notFoundResponse

    answerList = []

    for index, row in selected.iterrows():
        dataTable = {}
        # name = row['name'].split()
        # newName = row['name'].rsplit(' ', 1)[0]
        # i = 0
        # for element in name:
        #     locationType = name[i]
        #     i = i + 1
        # dataTable['name'] = newName
        dataTable['name'] = row['name']
        dataTable['city'] = row['cityName']
        dataTable['town'] = row['countryName']
        dataTable['address'] = row['address']
        dataTable['branchId'] = row['branchId']
        dataTable['phone'] = row['phone']
        dataTable['fax'] = row['fax']
        dataTable['lat'] = row['latitude']
        dataTable['long'] = row['longitude']
        answerList.append(dataTable)

    answer = {}
    answer["type"] = "maps"
    answer["response"] = "success"
    answer["location_type"] = "Atm"
    answer["img"] = "/content/img/atm.png"
    answer["arr"] = answerList
    
    return answer

# class ActionCanliDestek(Action):

#     def name(self) -> Text:
#         return "action_canli_destek"

#     def run(self, dispatcher: CollectingDispatcher,
#         tracker: Tracker,
#              domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

#         #counter = tracker.get_slot("counter")
#         senderId = tracker.sender_id
#         print("sender id: ", senderId, " is redirected to genesys agent-->", API_ENDPOINT.replace("{sender_id}", senderId))
#         #dispatcher.utter_template("utter_canli_destek", tracker)
#         headers = {'Content-type': 'application/json', 'Accept': 'text/plain'}
#         request = requests.put(url = API_ENDPOINT.replace("{sender_id}", senderId), headers=headers)
#         print("request answer: ", request.status_code, request.reason)

#         return []

class ActionSaat(Action):

    def name(self) -> Text:
        return "action_saat"

    def run(self, dispatcher: CollectingDispatcher,
        tracker: Tracker,
             domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        #dispatcher.utter_message("Hello World!")

        saat = "Saat: " + datetime.datetime.now().strftime("%H:%M:%S")
        dispatcher.utter_message(saat)

        return []

class ActionDoviz(Action):

    def name(self) -> Text:
        return "action_doviz"

    def run(self, dispatcher: CollectingDispatcher,
        tracker: Tracker,
             domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        exchangeRates = get_currency()

        currency = tracker.get_slot("doviz")
        amount = tracker.get_slot("miktar")

        from_doviz = tracker.get_slot('from_doviz')
        to_doviz = tracker.get_slot('to_doviz')

        if currency is None and to_doviz == "TL":
            currency = from_doviz

        if amount is None:
            amount = 1

        if currency is not None and not currency and currency not in exchangeRates:
            print(currency + " is not defined.")

        if amount is not None and currency is not None:
            exchangeRate = exchangeRates[currency]

            result = float(amount)
            result = round(result * float(exchangeRate['sellRate']), 5)
            result = float(result)
            result = "{:,.4f}".format(result)
            result = str(result).replace(".",",")

            now = datetime.datetime.now()
            currencydate= str(now.hour) + ":" + str(now.minute) + ":" + str(now.second) + " - " + str(now.day) + ":" + str(now.month) + ":" + str(now.year)
            
            if "USD" in exchangeRate['shortName']:
                exchangeRate['shortName'] = "Dolar"
                exchangeRate['symbol'] = "$"
            elif "EUR" in exchangeRate['shortName']:
                exchangeRate['shortName'] = "Euro"
                exchangeRate['symbol'] = "€"
            elif "ALT" in exchangeRate['shortName']:
                exchangeRate['shortName'] = "Altın"
                exchangeRate['symbol'] = "g"
            elif "GMS" in exchangeRate['shortName']:
                exchangeRate['shortName'] = "Gümüş"
                exchangeRate['symbol'] = "g"
            elif "PLT" in exchangeRate['shortName']:
                exchangeRate['shortName'] = "Platin"
                exchangeRate['symbol'] = "g"
            elif "ZCeyrek" in exchangeRate['shortName']:
                exchangeRate['shortName'] = "Çeyrek Altın"
                exchangeRate['symbol'] = "g"
            
            sellRate = float(exchangeRate['sellRate'])
            sellRate = "{:,.4f}".format(sellRate)
            sellRate = str(sellRate).replace(".",",")

            answer = {}
            answer['type'] = "currency"
            answer['currency'] = exchangeRate['shortName']
            answer['buyRate'] = exchangeRate['buyRate']
            answer['sellRate'] = sellRate
            answer['rate'] = exchangeRate['parity']
            answer['amount'] = str(amount)
            answer['result'] = str(result)
            answer['date'] = currencydate
            answer['increaseImage'] = "/content/img/increase.png"
            answer['decreaseImage'] = "/content/img/decrease.png"
            answer['targetSymbol'] = "₺"

            dispatcher.utter_custom_json(json.dumps(answer, ensure_ascii=False))

        elif currency is None and from_doviz is not None and to_doviz is not None:
            dispatcher.utter_message(str(from_doviz) + "-" + str(to_doviz) + " kuru hesaplanamamaktadır.")

        else:
            dispatcher.utter_message("Lütfen hesaplamak istediğiniz döviz türünü ve miktarını giriniz.")

        return [SlotSet("doviz", None), SlotSet("miktar", None), SlotSet("from_doviz", None), SlotSet("to_doviz", None)]

class ActionSube(Action):

    def name(self) -> Text:
        return "action_sube"

    def run(self, dispatcher: CollectingDispatcher,
        tracker: Tracker,
             domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        lokasyon_turu = tracker.get_slot("lokasyon_turu")
        print("Lokasyon ==> ", lokasyon_turu)
        latestMessage = tracker.latest_message['text']

        """Server'da loga print etmek için encode edilmeli..."""
        sehir = tracker.get_slot("sehir") if tracker.get_slot("sehir") is not None else None
        print("Sehir ==> ", sehir.encode('utf-8') if sehir is not None else None)
        semt = tracker.get_slot("semt") if tracker.get_slot("semt") is not None else None
        print("Semt slot ==> ", semt.encode('utf-8') if semt is not None else None)

        if lokasyon_turu is None or not lokasyon_turu or "sube" not in lokasyon_turu and "atm" not in lokasyon_turu and sehir is not None:
            # if semt is None or not semt:
            #     latestIntent = tracker.latest_message['intent']['name']
            #     lastText = latestMessage.split()

            #     if len(lastText)>1 and latestIntent == 'sehir':
            #         semt = lastText[1]
            answer = find_branch(sehir, semt)

            if answer["response"] == "error":
                if sehir is not None and semt is None:
                    sehir = capitalize(sehir)
                    # dispatcher.utter_message(sehir + " şehrinde şubemiz bulunmamaktadır.")
                    dispatcher.utter_message("Belirttiğiniz konumda şubemiz bulunmamaktadır.")
                    return [SlotSet("lokasyon_turu", None), SlotSet("sehir", None), SlotSet("semt", None)]
                if semt is not None and sehir is None:
                    semt = capitalize(semt)
                    # dispatcher.utter_message(semt + " ilçesinde şubemiz bulunmamaktadır.")
                    dispatcher.utter_message("Belirttiğiniz konumda şubemiz bulunmamaktadır.")
                    return [SlotSet("lokasyon_turu", None), SlotSet("sehir", None), SlotSet("semt", None)]
                if sehir is not None and semt is not None:
                    sehir = capitalize(sehir)
                    semt = capitalize(semt)
                    # dispatcher.utter_message(sehir + " " + semt + " bölgesinde şubemiz bulunmamaktadır.")
                    dispatcher.utter_message("Belirttiğiniz konumda şubemiz bulunmamaktadır.")
                    return [SlotSet("lokasyon_turu", None), SlotSet("sehir", None), SlotSet("semt", None)]
            if len(answer["arr"]) > 3 and semt is None:
                dispatcher.utter_message("Lütfen ilçe giriniz.")
                return [SlotSet("sehir", sehir)]
            elif len(answer) > 0:
                dispatcher.utter_custom_json(json.dumps(answer, ensure_ascii=False))
                return [SlotSet("lokasyon_turu", None), SlotSet("sehir", None), SlotSet("semt", None)]
            else:
                dispatcher.utter_message("Lütfen daha sonra tekrar deneyiniz: " + latestMessage)
                return [SlotSet("lokasyon_turu", None), SlotSet("sehir", None), SlotSet("semt", None)]
        
        if lokasyon_turu is not None:
            if sehir is None and semt is None:
                dispatcher.utter_message("Lütfen il ve ilçe/semt bilgisi giriniz. (Örnek: İstanbul Üsküdar)")
                return [SlotSet("sehir", sehir)]

            # if sehir is not None and semt is None or not semt:
            #     latestIntent = tracker.latest_message['intent']['name']
            #     lastText = latestMessage.split()
            #     if len(lastText)>1 and latestIntent == 'sehir':
            #         semt = lastText[1]
            #     print("Semt ==> ", semt)

            if sehir is not None or semt is not None:
                if "sube" in lokasyon_turu:
                    answer = find_branch(sehir, semt)
                    if answer["response"] == "error":
                        if sehir is not None and semt is None:
                            sehir = capitalize(sehir)
                            # dispatcher.utter_message(sehir + " şehrinde şubemiz bulunmamaktadır.")
                            dispatcher.utter_message("Belirttiğiniz konumda şubemiz bulunmamaktadır.")
                            return [SlotSet("lokasyon_turu", None), SlotSet("sehir", None), SlotSet("semt", None)]
                        if semt is not None and sehir is None:
                            semt = capitalize(semt)
                            # dispatcher.utter_message(semt + " ilçesinde şubemiz bulunmamaktadır.")
                            dispatcher.utter_message("Belirttiğiniz konumda şubemiz bulunmamaktadır.")
                            return [SlotSet("lokasyon_turu", None), SlotSet("sehir", None), SlotSet("semt", None)]
                        if sehir is not None and semt is not None:
                            sehir = capitalize(sehir)
                            semt = capitalize(semt)
                            # dispatcher.utter_message(sehir + " " + semt + " bölgesinde şubemiz bulunmamaktadır.")
                            dispatcher.utter_message("Belirttiğiniz konumda şubemiz bulunmamaktadır.")
                            return [SlotSet("lokasyon_turu", None), SlotSet("sehir", None), SlotSet("semt", None)]
                    if len(answer["arr"]) > 3 and semt is None:
                        dispatcher.utter_message("Lütfen ilçe giriniz.")
                        return [SlotSet("sehir", sehir)]
                    elif len(answer) > 0:
                        dispatcher.utter_custom_json(json.dumps(answer, ensure_ascii=False))
                        return [SlotSet("lokasyon_turu", None), SlotSet("sehir", None), SlotSet("semt", None)]
                    else:
                        dispatcher.utter_message("Lütfen daha sonra tekrar deneyiniz: " + latestMessage)
                        return [SlotSet("lokasyon_turu", None), SlotSet("sehir", None), SlotSet("semt", None)]

                elif "atm" in lokasyon_turu:
                    answer = find_atm(sehir, semt)
                    if answer["response"] == "error":
                        if sehir is not None and semt is None:
                            sehir = capitalize(sehir)
                            # dispatcher.utter_message(sehir + " şehrinde atm bulunmamaktadır.")
                            dispatcher.utter_message("Belirttiğiniz konumda atm bulunmamaktadır.")
                            return [SlotSet("lokasyon_turu", None), SlotSet("sehir", None), SlotSet("semt", None)]
                        if semt is not None and sehir is None:
                            semt = capitalize(semt)
                            # dispatcher.utter_message(semt + " ilçesinde atm bulunmamaktadır.")
                            dispatcher.utter_message("Belirttiğiniz konumda atm bulunmamaktadır.")
                            return [SlotSet("lokasyon_turu", None), SlotSet("sehir", None), SlotSet("semt", None)]
                        if sehir is not None and semt is not None:
                            sehir = capitalize(sehir)
                            semt = capitalize(semt)
                            # dispatcher.utter_message(sehir + " " + semt + " bölgesinde atm bulunmamaktadır.")
                            dispatcher.utter_message("Belirttiğiniz konumda atm bulunmamaktadır.")
                            return [SlotSet("lokasyon_turu", None), SlotSet("sehir", None), SlotSet("semt", None)]
                    if len(answer["arr"]) > 3 and semt is None:
                        dispatcher.utter_message("Lütfen ilçe giriniz.")
                        return [SlotSet("sehir", sehir)]
                    elif len(answer) > 0:
                        dispatcher.utter_custom_json(json.dumps(answer, ensure_ascii=False))
                        return [SlotSet("lokasyon_turu", None), SlotSet("sehir", None), SlotSet("semt", None)]
                    else:
                        dispatcher.utter_message("Lütfen daha sonra tekrar deneyiniz: " + latestMessage)
                        return [SlotSet("lokasyon_turu", None), SlotSet("sehir", None), SlotSet("semt", None)]

        return []

class ActionStartForm(Action):

    def name(self) -> Text:
        return "action_start_form"

    def run(self, dispatcher: CollectingDispatcher,
        tracker: Tracker,
             domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        intent = tracker.latest_message.get("intent", {}).get("name")
        print("intent: ", intent)
        form = tracker.active_form.get("name")
        print("active form: ", form)

        if intent == "finansman_hesaplama":
            dispatcher.utter_template("utter_finansman_hesaplama_form", tracker)
            return [SlotSet("finansman_turu", None), SlotSet("miktar", None), SlotSet("vade", None), Form(None)]

        if intent == "kar_payi_hesaplama":
            dispatcher.utter_template("utter_kar_payi_hesaplama_form", tracker)
            return [SlotSet("doviz", None), SlotSet("miktar", None), SlotSet("vade", None), Form(None)]

        return [Form(None)]

class FinansmanHesaplamaForm(FormAction):
    """Example of a custom form action"""

    def name(self) -> Text:
        """Unique identifier of the form"""

        return "form_finansman"

    @staticmethod
    def required_slots(tracker: Tracker) -> List[Text]:
        """A list of required slots that the form has to fill"""

        return ["finansman_turu", "vade", "miktar"]

    def slot_mappings(self) -> Dict[Text, Union[Dict, List[Dict]]]:
        """A dictionary to map required slots to
            - an extracted entity
            - intent: value pairs
            - a whole message
            or a list of them, where a first match will be picked"""

        return {
            "finansman_turu": self.from_entity(entity="finansman_turu", intent= ["finansman_hesaplama"]),

            "vade":  [ self.from_entity(entity="sayi"),
                       self.from_text(intent=["sayi"])],

            "miktar": [ self.from_entity(entity="sayi"),
                       self.from_text(intent=["sayi"])],
        }

    def submit(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict]:
        """Define what the form has to do
            after all required slots are filled"""

        miktar = int(tracker.get_slot('miktar'))
        vade = tracker.get_slot('vade')
        finansman = tracker.get_slot('finansman_turu')

        instalmentAmount = "".join([{',':'.','.':','}.get(x,x) for x in str("{:,.2f}".format(11066.005742682561357330022126))])
        # profitRate = "{:,.2f}".format(0.79000)
        profitRate = "".join([{',':'.','.':','}.get(x,x) for x in str("{:,.2f}".format(0.79000))])

        if "tasit_ikinci_el" in finansman:
            finansman = "taşıt ikinci el"
        if "tasit" in finansman:
            finansman = "taşıt"
        if "isyeri" in finansman:
            finansman = "iş yeri"

        miktar = '{:,}'.format(miktar).replace(",",".")
        
        title = str(miktar) + " TL'lik " + str(vade) + " aylık " + finansman + " finansmanına ait taksit tutarı ve kar oranınızı aşağıda paylaşıyorum."
        menu = [ {"title": "Taksit Tutarı", "value": " " + str(instalmentAmount) + " TL"}, {"title": "Kar Oranı", "value": " %" + str(profitRate) } ]
        button = {"title": "Ödeme Planı", "src": "https://www.vakifkatilim.com.tr/tr/bireysel/finansman-turleri/finansman-hesaplama?loantype=K&loanAmount=250.000&InstallmentAmount=60", "img": "/content/img/calculationPlan.png" }

        result = {}
        result['type'] = "calculationResults"
        result['title'] = title
        result['menu'] = menu
        result['button'] = button

            # answer = {}
            # #Döviz Türü
            # answer["fec"] = dataTable['fec']
            # #Brüt Kar Payı
            # answer["grossProfitShare"] = dataTable['grossProfitShare']
            # #Net Kar Payı
            # answer["netProfitShare"] = dataTable['netProfitShare']

        dispatcher.utter_custom_json(json.dumps(result, ensure_ascii=False))
        return [SlotSet('finansman_turu', None), SlotSet('vade', None), SlotSet('miktar', None)]

    # @staticmethod
    # def is_int(string: Text) -> bool:
    #     """Check if a string is an integer"""

    #     try:
    #         int(string)
    #         return True
    #     except ValueError:
    #         return False

#    def validate(self, dispatcher, tracker, domain):
#        print("validate finansman_form")
#        try:
#            return super().validate(dispatcher, tracker, domain)
#        except ActionExecutionRejection as e:
#            # could not extract entity
#            dispatcher.utter_template("utter_finansman_hesaplama_parameters", tracker)
#            return []

    def validate_vade(
        self,
        value: Text,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Optional[Text]:
        """Validate num_people value."""

        try:
            print("validate vade")
            if len(value) > 1:
                value = value.split()
                value = value[0]
            productType = tracker.get_slot('finansman_turu')
            vade = str(value)
            if (vade.isdigit()):
                if productType is not None and int(value) > 180 and "konut" in productType:
                    dispatcher.utter_message("Konut finansmanında vade 180'den az olmalıdır.")
                    return {"vade": None}
                elif productType is not None and int(value) > 48 and "tasit" in productType:
                    dispatcher.utter_message("Taşıt (0 km) finansmanında vade 48'den az olmalıdır.")
                    return {"vade": None}
                elif productType is not None and int(value) > 36 and "tasit_ikinci_el" in productType:
                    dispatcher.utter_message("Taşıt (2.el) finansmanında vade 36'dan az olmalıdır.")
                    return {"vade": None}
                elif productType is not None and int(value) > 60 and "isyeri" in productType:
                    dispatcher.utter_message("İşyeri finansmanında vade 60'tan az olmalıdır.")
                    return {"vade": None}
                elif productType is not None and int(value) > 60 and "arsa" in productType:
                    dispatcher.utter_message("Arsa finansmanında vade 60'tan az olmalıdır.")
                    return {"vade": None}
                else:
                    return {"vade": value}
            else:
                dispatcher.utter_message("Girdiğiniz vade geçerli değildir.")
                return {"vade": None}
        except:
            return {"vade": None}

    def validate_miktar(
        self,
        value: Text,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Optional[Text]:
        """Validate num_people value."""

        try:
            print("validate miktar")
            miktar = str(value)
            if (miktar.isdigit()):
                print("digit", miktar.isdigit())
                return {"miktar": value}
            else:
#                dispatcher.utter_template("utter_wrong_vade", tracker)
                dispatcher.utter_message("Girdiğiniz finansman tutarı geçerli değildir.")
                # validation failed, set slot to None
                return {"miktar": None}
        except:
            return {"miktar": None}

class KarpayiHesaplamaForm(FormAction):
    """Example of a custom form action"""

    def name(self) -> Text:
        """Unique identifier of the form"""

        return "form_karpayi"

    @staticmethod
    def required_slots(tracker: Tracker) -> List[Text]:
        """A list of required slots that the form has to fill"""

        return ["doviz", "vade", "miktar"]

    def slot_mappings(self) -> Dict[Text, Union[Dict, List[Dict]]]:
        """A dictionary to map required slots to
            - an extracted entity
            - intent: value pairs
            - a whole message
            or a list of them, where a first match will be picked"""

        return {
            "doviz": [self.from_entity(entity="doviz", intent=["kar_payi_hesaplama"]),
                      self.from_entity(entity="doviz", intent=["doviz_hesaplama"])],

            "vade":  [ self.from_entity(entity="sayi"),
                       self.from_text(intent=["sayi"])],
                      
            "miktar": [self.from_entity(entity="sayi"),
                       self.from_text(intent=["sayi"])]
        }

    def submit(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict]:
        """Define what the form has to do
            after all required slots are filled"""

        miktar = int(tracker.get_slot('miktar'))
        vade = tracker.get_slot('vade')
        doviz = tracker.get_slot('doviz')
        vade_turu = tracker.get_slot('vade_turu')
        # result =  ' Tutar : ' +  str(int(tracker.get_slot('miktar'))) + "  " + tracker.get_slot('doviz')
        # result = result + '\n Vade : ' +  str(vade)
        # result = result + " \n Kar payı : " + str(toplam*1.1)
        # # utter submit template
        # dispatcher.utter_message(result)
        vade_tip = " "
        amountType = " "

        if "ALT" in doviz:
            amountType = " gram "
        else:
            amountType = amountType

        if "1 ay" in vade:
            maturityTerm = 31
        elif "3 ay" in vade:
            maturityTerm = 91
        elif "6 ay" in vade:
            maturityTerm = 180
        elif "yıllık" in vade:
            maturityTerm = 364
        elif "1 yıl ve üzeri" in vade:
            maturityTerm = 366
        elif "gün" in vade:
            vade = vade.split()
            maturityTerm = vade[0]
            vade = maturityTerm 
            vade_tip = "gün"
        elif vade_turu is not None and "gun" in vade_turu and "ay" not in vade:
            if len(vade) > 1:
                vade = vade.split()
                maturityTerm = vade[0]
                vade = maturityTerm 
            else:
                maturityTerm = vade
            vade_tip = "gün"
        elif vade_turu is not None and "ay" in vade_turu and "gün" not in vade:
            if len(vade) > 1:
                vade = vade.split()
                maturityTerm = vade[0]
                vade = maturityTerm 
            else:
                maturityTerm = vade
            maturityTerm = int(maturityTerm) * 30
            vade_tip = "ay"
        else:
            if len(vade) > 1:
                vade = vade.split()
                maturityTerm = vade[0]
                vade = maturityTerm 
            else:
                maturityTerm = vade
            maturityTerm = int(maturityTerm) * 30
            vade_tip = "ay"
            
        miktar_input = '{:,}'.format(miktar).replace(",",".")

        netProfitShare = "".join([{',':'.','.':','}.get(x,x) for x in str("{:,.2f}".format(miktar))])
        # netProfitShareYearly = "{:,.2f}".format(int(maturityTerm))
        netProfitShareYearly = "".join([{',':'.','.':','}.get(x,x) for x in str("{:,.2f}".format(int(maturityTerm)))])

        title = str(miktar_input) + amountType + str(doviz) + " için " + str(vade) + " " + vade_tip + " vadeli kar oranlarınızı aşağıda paylaşıyorum."
        menu = [ {"title": "Net Oran", "value": " %" + str(netProfitShareYearly) }, {"title": "Net Kar", "value": " " + str(netProfitShare) } ]
        button = {"title": "Detaylı Bilgi", "src": "https://www.vakifkatilim.com.tr/tr/bireysel/hesaplar/kar-payi-hesaplama?fec=1&grossAmount=250.000&maturityTerm=180", "img": "/content/img/detaylibilgi.png" }
        info = "Hesaplama aracındaki sonuçlar, vadesi bugün dolmuş hesaplara dağıtılan kâr paylarına göre hesaplanmaktadır. Hesaplama sonuçları Vakıf Katılım Bankası A.Ş. adına geleceğe yönelik bir taahhüt içermemektedir."

        result = {}
        result['type'] = "calculationResults"
        result['title'] = title
        result['menu'] = menu
        result['button'] = button
        result['info'] = info  
        
        dispatcher.utter_custom_json(json.dumps(result, ensure_ascii=False))
        return [SlotSet('doviz', None), SlotSet('vade', None), SlotSet('miktar', None), SlotSet('vade_turu', None)]

    def validate_vade(
        self,
        value: Text,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Optional[Text]:

        try:
            print("validate vade")
            doviz = tracker.get_slot('doviz')
            vade_turu = tracker.get_slot('vade_turu')
            if vade_turu is not None and "gun" in vade_turu and "ALT" in doviz:
                if "ay" not in value:
                    vade = value
                    vade = vade.split()
                    maturityTerm = vade[0]
                    if int(maturityTerm) < 91:
                        dispatcher.utter_message("91 -364 gün arasında değer giriniz.")
                        return {"vade": None}
                    if int(maturityTerm) > 364:
                        dispatcher.utter_message("Maksimum 364 gün vadeli Altın Katılma Hesabı açılabilmektedir.")
                        return {"vade": None}
                    return {"vade": value}
                return {"vade": value}
            elif vade_turu is not None and "gun" in vade_turu and ("TL" in doviz or "USD" in doviz or "EUR" in doviz):
                if "ay" not in value:
                    vade = value
                    vade = vade.split()
                    maturityTerm = vade[0]
                    if int(maturityTerm) < 31:
                        dispatcher.utter_message("TL, USD ve EUR günlük kar payı hesaplamaları en az 31 gün olarak yapılmaktadır.")
                        return {"vade": None}
                    return {"vade": value}
                return {"vade": value}
            else:
                return {"vade": value}
        except:
            return {"vade": None}

    def validate_miktar(
        self,
        value: Text,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Optional[Text]:

        try:
            print("validate miktar")
            miktar = str(value)
            if (miktar.isdigit()):
                currencyType = tracker.get_slot('doviz')
                if currencyType is not None and int(miktar) < 250 and "TL" in currencyType:
                    dispatcher.utter_message("Katılma Hesabı en az 250 TL ile açılmaktadır.")
                    return {"miktar": None}
                if currencyType is not None and int(miktar) < 250 and "USD" in currencyType:
                    dispatcher.utter_message("Katılma Hesabı en az 250 USD ile açılmaktadır.")
                    return {"miktar": None}
                if currencyType is not None and int(miktar) < 250 and "EUR" in currencyType:
                    dispatcher.utter_message("Katılma Hesabı en az 250 EUR ile açılmaktadır.")
                    return {"miktar": None}
                if currencyType is not None and int(miktar) < 50 and "ALT" in currencyType:
                    dispatcher.utter_message("Altın Katılma Hesabı minimum 50 gram ile açılmaktadır.")
                    return {"miktar": None}
                return {"miktar": value}
            else:
                dispatcher.utter_message("Girdiğiniz kar payı tutarı geçerli değildir.")
                return {"miktar": None}
        except:
            return {"miktar": None}