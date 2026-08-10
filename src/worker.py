import pika
import json
import traceback
import sys
import os
from database import update_task_status, increment_task_attempts, get_task
from ingest import process_pdf

MAX_RETRIES = 3

def setup_queues(channel):
    # Declare Dead Letter Queue
    channel.queue_declare(queue='pdf_tasks_dlq', durable=True)
    
    # Declare main queue with Dead Letter Exchange
    args = {
        'x-dead-letter-exchange': '',
        'x-dead-letter-routing-key': 'pdf_tasks_dlq'
    }
    channel.queue_declare(queue='pdf_tasks', durable=True, arguments=args)

def process_message(ch, method, properties, body):
    try:
        data = json.loads(body)
        pdf_id = data.get("pdf_id")
        if not pdf_id:
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            return

        print(f"\n[*] Received task for pdf_id: {pdf_id}")

        task = get_task(pdf_id)
        if not task:
            print(f"[!] Task not found in DB for {pdf_id}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            return

        attempts = increment_task_attempts(pdf_id)
        print(f"[*] Attempt {attempts}/{MAX_RETRIES} for {pdf_id}")
        
        if attempts > MAX_RETRIES:
            print(f"[!] Max retries exceeded for {pdf_id}. Moving to DLQ.")
            update_task_status(pdf_id, 'FAILED', 'Max retries exceeded')
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            return

        update_task_status(pdf_id, 'PROCESSING')

        try:
            # Process the PDF
            process_pdf(pdf_id, task['filename'])
            
            # Success
            update_task_status(pdf_id, 'INDEXED')
            ch.basic_ack(delivery_tag=method.delivery_tag)
            print(f"[*] Successfully processed {pdf_id}")
            
        except Exception as e:
            error_msg = traceback.format_exc()
            print(f"[!] Error processing {pdf_id}: {e}")
            if attempts >= MAX_RETRIES:
                update_task_status(pdf_id, 'FAILED', str(e))
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            else:
                update_task_status(pdf_id, 'UPLOADED', str(e)) # revert to UPLOADED so it can be picked up
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

    except Exception as e:
        print(f"[!] Fatal error in worker callback: {e}")
        # Reject without requeue if it's completely malformed
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

def main():
    connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
    channel = connection.channel()
    
    setup_queues(channel)
    
    # Process one message at a time
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue='pdf_tasks', on_message_callback=process_message)
    
    print(' [*] Waiting for messages. To exit press CTRL+C')
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        print('\n[*] Interrupted')
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)

if __name__ == '__main__':
    main()