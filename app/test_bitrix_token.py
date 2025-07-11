import requests

webhook_url = 'https://b24-aq3cu2.bitrix24.ru/rest/1/cuq4un14clczb58j/calendar.event.delete.json'

data = {'id': 2}

respons = requests.post(webhook_url, json=data)
event = respons.json()
print(event)


#calendar.event.delete
#calendar.event.getbyid