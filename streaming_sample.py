import requests
import json


API_KEY = "my-api-key"
LIST_MODELS = {
    "model-name":{
        "model-id": "model-id",
        "model-url": "https://mycompany.com/api/v1/run/session_id"
    },
    "Gauss2.3":{
        "model-id": "model-id",
        "model-url": "https://mycompany.com/api/v1/run/session_id"
    },
    "Gauss2.3 Think":{
        "model-id": "model-id",
        "model-url": "https://mycompany.com/api/v1/run/session_id"
    },
    "GaussO Flash":{
        "model-id": "model-id",
        "model-url": "https://mycompany.com/api/v1/run/session_id"
    },
    "GaussO Flash (S)":{
        "model-id": "model-id",
        "model-url": "https://mycompany.com/api/v1/run/session_id"
    },
    "GaussO4":{
        "model-id": "model-id",
        "model-url": "https://mycompany.com/api/v1/run/session_id"
    },
    "GaussO4 Thinking":{
        "model-id": "model-id",
        "model-url": "https://mycompany.com/api/v1/run/session_id"
    },
}



# Params
model_name = "model-name"
system_prompt = ""
user_prompt = "who are you?"



headers = {
    'Content-Type': 'application/json',
    'x-api-key': API_KEY
}

params = {
    'stream': 'true', 
}

json_data = {
    'component_inputs':{
        LIST_MODELS[model_name]["model-id"] : {
            'input_value': user_prompt,
            'max_retries': 0,
            'parameters': '{"temperature":0, "top_p": 0.95, "extra_body": {"repetition_penalty":1.05}}',
            'stream': True,
            'system_message': system_prompt,
        }
    }
}

with requests.post(
    url = LIST_MODELS[model_name]["model-url"],
    params=params,
    headers=headers,
    json=json_data,
    stream=True,
    verify=False,
    proxies={"https": None}
) as response:
    for line in response.iter_lines():
        if not line: continue

        decoded_line = json.loads(line.decode("utf-8"))
        if 'event' in decoded_line:
            if decoded_line['event'] == 'token':
                chunk = decoded_line["data"]["chunk"]
                print(chunk, end='')


print("")

