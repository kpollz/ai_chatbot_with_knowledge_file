import requests


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
    'stream': 'false', 
}

json_data = {
    'component_inputs':{
        LIST_MODELS[model_name]["model-id"] : {
            'input_value': user_prompt,
            'max_retries': 0,
            'parameters': '{"temperature":0, "top_p": 0.95, "extra_body": {"repetition_penalty":1.05}}',
            'stream': False,
            'system_message': system_prompt,
        }
    }
}

response = requests.post(
    LIST_MODELS[model_name]["model-url"],
    params=params,
    headers=headers,
    json=json_data,
)

# The response.json() is like below
# response.json() = {
#     'session_id': '{session_id}',
#     'outputs': [{'inputs': {},
#                  'outputs':[{
#                      'results':{
#                          'text': {
#                              'text': '{answer-of-llms}',
#                              'sender':None,
#                              'sender_name': None,
#                              'timestamp': '{timestamp}',
#                              'error': False
#                          }
#                      },
#                      'timedelta': None,
#                      'duration': None,
#                      'component_display_name': 'Text Output',
#                      'component_id': '{component_id}' 
#                  }],
#                  'legacy_components': [],
#                  'warning': None}]}
