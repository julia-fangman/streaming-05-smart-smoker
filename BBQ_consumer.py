# Julia Fangman
# June 5, 2024

import pika
import sys
import os
import time
import csv
import webbrowser
import traceback
from collections import deque
from datetime import datetime
from util_logger import setup_logger

logger, logname = setup_logger(__file__)

def offer_rabbitmq_admin_site():
   """Offer to open the RabbitMQ Admin website."""
   ans = input("Would you like to monitor RabbitMQ queues? y or n ")
   print()
   if ans.lower() == "y":
       webbrowser.open_new("http://localhost:15672/#/queues")
       logger.info("Opened RabbitMQ")

SMOKER_MAX_LEN = 5  # 2.5 min * 1 reading/0.5 min
FOOD_MAX_LEN = 20   # 10 min * 1 reading/0.5 min

SMOKER_TEMP_DROP_THRESHOLD = 15.0  # degrees F
FOOD_TEMP_STALL_THRESHOLD = 1.0    # degrees F

smoker_temps = deque(maxlen=SMOKER_MAX_LEN)
food_A_temps = deque(maxlen=FOOD_MAX_LEN)
food_B_temps = deque(maxlen=FOOD_MAX_LEN)

def check_smoker_alert():
    """Check if the smoker temperature decreases by more than the threshold in the given time window."""
    if len(smoker_temps) == SMOKER_MAX_LEN:
        initial_temp = smoker_temps[0][1]
        latest_temp = smoker_temps[-1][1]
        if initial_temp - latest_temp >= SMOKER_TEMP_DROP_THRESHOLD:
            alert_message = f"Smoker Alert! Temperature dropped by {initial_temp - latest_temp}F in 2.5 minutes."
            print(alert_message)
            logger.info(alert_message)

def check_food_stall(deque, food_name):
    """Check if the food temperature changes less than the threshold in the given time window."""
    if len(deque) == FOOD_MAX_LEN:
        initial_temp = deque[0][1]
        latest_temp = deque[-1][1]
        if abs(initial_temp - latest_temp) <= FOOD_TEMP_STALL_THRESHOLD:
            alert_message = f"Food Stall Alert! {food_name} temperature changed by {abs(initial_temp - latest_temp)}F in 10 minutes."
            print(alert_message)
            logger.info(alert_message)

def listen_for_tasks():
    """ Continuously listen for task messages on named queues."""
    connection = None
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(host="localhost"))
        channel = connection.channel()

        queues = ["01-smoker", "02-food-A", "02-food-B"]
        for queue_name in queues:
            channel.queue_declare(queue=queue_name, durable=True)

        def callback(ch, method, properties, body):
            """Define behavior on getting a message."""
            message = eval(body.decode())
            timestamp, temp = message
            timestamp = datetime.strptime(timestamp, '%m/%d/%y %H:%M:%S')


            if method.routing_key == "01-smoker":
                smoker_temps.append((timestamp, temp))
                check_smoker_alert()
            elif method.routing_key == "02-food-A":
                food_A_temps.append((timestamp, temp))
                check_food_stall(food_A_temps, "Food A")
            elif method.routing_key == "02-food-B":
                food_B_temps.append((timestamp, temp))
                check_food_stall(food_B_temps, "Food B")

            ch.basic_ack(delivery_tag=method.delivery_tag)

        channel.basic_qos(prefetch_count=1)
        for queue_name in queues:
            channel.basic_consume(queue=queue_name, on_message_callback=callback)

        print(" [*] Ready for work. To exit press CTRL+C")
        channel.start_consuming()
    
    except pika.exceptions.AMQPConnectionError as e:
        logger.error(f"Connection error: {e}")
    except pika.exceptions.AMQPChannelError as e:
        logger.error(f"Channel error: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        traceback.print_exc()
    finally:
        if connection and not connection.is_closed:
            connection.close()

if __name__ == "__main__":
    try:
        offer_rabbitmq_admin_site()
        listen_for_tasks()
    except KeyboardInterrupt:
        print("Interrupted")
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)
