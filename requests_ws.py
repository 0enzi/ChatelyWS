from rsa import verify
import requests

def get_request(inbox_hash, token):
    """
    Get request
    """
    try:
        response = requests.get(f'http://127.0.0.1:8000/api/v1/chat/{inbox_hash}', headers={'Authorization': 'Bearer ' + token}, verify=False)
        return response.json(), response.status_code
    except Exception as e:
        print(e)
        return None

# print(get_request('27-1', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE2NTgyNDg2NzksInN1YiI6InsndXNlcm5hbWUnOiAnYWRtaW5AY2hhdGVseS5pbycsICd1c2VyX2lkJzogMjd9In0.0mgIZHbpMq2dwqLCJ7D2Izwyec0v47qECal19V98u58'))

# headers = {
#   'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.12; rv:55.0) Gecko/20100101 Firefox/55.0',
# }
# pload = {'key':'value'}
# r = requests.post('https://URL', data=pload, headers=headers)
# print(r.text)

def verify_inbox(inbox_hash, token):
    """
    Get request
    """
    try:
        response = requests.get(f'http://127.0.0.1:8000/api/v1/chat/{inbox_hash}', headers={'Authorization': 'Bearer ' + token}, verify=False)
        
        if response.status_code == 200:
            return True
    except Exception as e:
        print(e)
        return None
    return False

verify_inbox('1-27', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE2NTgyNDg2NzksInN1YiI6InsndXNlcm5hbWUnOiAnYWRtaW5AY2hhdGVseS5pbycsICd1c2VyX2lkJzogMjd9In0.0mgIZHbpMq2dwqLCJ7D2Izwyec0v47qECal19V98u58')
