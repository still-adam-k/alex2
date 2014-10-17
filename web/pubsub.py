from json import dumps, loads
from pika import BlockingConnection, URLParameters
from pika.exceptions import AMQPError
from spinner import spin
from sys import stderr

class PubSubError(Exception):
    pass

class PubSub:
    def __init__(self, url, exchange):
        self.conn = BlockingConnection(URLParameters(url))
        self.exchange = exchange
        self._create_channel_and_exchange()

    def publish(self, topic, fact):
        self._check_channel()
        self.channel.basic_publish(exchange=self.exchange,
                                   routing_key=topic,
                                   body=dumps(fact))

    def subscribe(self, topic):
        self._check_channel()
        queue = self.channel.queue_declare(exclusive=False).method.queue
        self.channel.queue_bind(exchange=self.exchange, queue=queue,
                                routing_key=topic)
        return queue

    def fetch_from_sub(self, topic, queue, timeout, spin=spin):
        self._check_channel()
        result = spin(lambda: self._check_queue(queue), timeout)
        return self._safe_loads(result)

    def consume(self, topic, consumer):
        self._check_channel()
        def rabbit_consumer(channel, method, properties, body):
            consumer(method.routing_key, loads(body))
        queue = self.subscribe(topic)
        self.channel.basic_consume(rabbit_consumer, queue=queue, no_ack=True)
        self.channel.start_consuming()

    def _check_queue(self, queue):
        try:
            return self.channel.basic_get(queue=queue, no_ack=True)[2]
        except AMQPError as e:
            raise PubSubError(e)

    def _safe_loads(self, value):
        if value is None:
            return None
        else:
            return loads(value)

    def _check_channel(self):
        if not self.channel.is_open:
            stderr.write('Channel was closed, reopening')
            self._create_channel_and_exchange()
            if not self.channel.is_open:
                raise CannotReopenChannelError

    def _create_channel_and_exchange(self):
        self.channel = self.conn.channel()
        self.channel.exchange_declare(exchange=self.exchange, type='topic')

def CannotReopenChannelError(Exception):
    pass
            
