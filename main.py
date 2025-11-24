import paho.mqtt.client as mqtt
import json
import ssl
import time
from datetime import datetime
print("runs")
#config
broker = "6dee21bc18054d9db4d08e6a88cad0ca.s1.eu.hivemq.cloud"
port =8883
user ="RaspberryPi"
password ="A123a321"
#gateway topic config
topic_incoming ="node/data"
topic_outgoing="cloud/processed"
#teheee
#a colorful bunch of functions for mqtt
def on_connect (client, userdata, flags, rc):
		if rc ==0:
			print(f"gateway connected")
			client.subscribe(topic_incoming)
		else:
			print(f"failed to connect with code {rc}")
def on_message(client, userdata, msg):
	try:
		payload_str = msg.payload.decode()
		print(f"msg received on {msg.topic}:{payload_str}")
		try:
			data =json.loads(payload_str)
			data["gateway_id"]="rasPi_001"
			data["processed_at"]=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
			new_payload =json.dumps(data)
		except json.JSONDecodeError:
			new_payload = payload_str
			
		client.publish(topic_outgoing, new_payload)
		print(f"[OUT]sent to somewhere how tf am i supposed to know {topic_outgoing}:{new_payload}")
	except Exception as e:
		print(f"error u lazy fuckass:{e}")
	





def setup_gateway():
	client =mqtt.Client()
	client.username_pw_set(user,password)
	client.tls_set(cert_reqs=ssl.CERT_NONE)
	client.tls_insecure_set(True)
	client.on_connect=on_connect
	client.on_message=on_message
	return client

def main():
	gateway=setup_gateway()
	print("Starting mqtt gateway")
	gateway.connect(broker,port,60)
	gateway.loop_forever()
if __name__ == "__main__":
	main()
	
			
