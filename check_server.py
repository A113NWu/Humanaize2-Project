import requests
import time

for i in range(30):
    time.sleep(3)
    try:
        r = requests.post('http://127.0.0.1:8080/completion', json={'prompt': 'test', 'n_predict': 5}, timeout=5)
        print(f'Attempt {i+1}: Status {r.status_code}')
        if r.status_code == 200:
            print('Server is ready!')
            print('Response:', r.text[:200])
            break
    except Exception as e:
        print(f'Attempt {i+1}: {e}')