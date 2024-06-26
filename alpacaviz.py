import asyncio
import datetime
import json
import math
import random
import string
import pandas as pd
import streamlit as st
from confluent_kafka import Consumer, TopicPartition
import altair as alt


config_dict = {
    "bootstrap.servers": st.secrets["BOOTSTRAP_URL"],
    "sasl.mechanisms": "PLAIN",
    "security.protocol": "SASL_SSL",
    "auto.offset.reset": "earliest",
    "session.timeout.ms": "45000",
    "sasl.username": st.secrets["SASL_USERNAME"],
    "sasl.password": st.secrets["SASL_PASSWORD"],
    "group.id": "consumer_for_stocks",
}
# https://stackoverflow.com/questions/38032932/attaching-kafaconsumer-assigned-to-a-specific-partition


st.title("Stock Price Averages")
st.write("View a simulation of tumbling averages for SPY stock.")
my_slot1 = st.empty()

option = st.selectbox(
    "Start viewing stock for:",
    (["SPY"]),
    index=None,
)


async def main():
    if isinstance(option, str):

        await display_quotes(placeholder)


async def display_quotes(component):
    consumer = Consumer(config_dict)

    partition = TopicPartition(f"tumble_interval_SPY", 0, 7)
    consumer.assign([partition])
    consumer.seek(partition)
    message_count = 0
    component.empty()
    price_history = []
    window_history = []

    while message_count <= 80:
        try:
            # print("Polling topic")
            msg = consumer.poll(1)

            # print("Pausing")
            await asyncio.sleep(0.5)

            print("Received message: {}".format(msg))
            if msg is None:
                continue

            elif msg.error():
                print("Consumer error: {}".format(msg.error()))

            with component:
                data_string_with_bytes_mess = "{}".format(msg.value())
                data_string_without_bytes_mess = data_string_with_bytes_mess.replace(
                    data_string_with_bytes_mess[0:22], ""
                )
                data_string_without_bytes_mess = data_string_without_bytes_mess[:-1]
                quote_dict = json.loads(data_string_without_bytes_mess)

                last_price = quote_dict["price"]

                window_end = quote_dict["window_end"]

                window_end_string = window_end[:0] + window_end[10:]

                price_history.append(last_price)
                window_history.append(window_end_string)
                message_count += 1

                data = pd.DataFrame(
                    {
                        "price_in_USD": price_history,
                        "window_end": window_history,
                    },
                )

                domain_end = max(price_history)
                domain_start = min(price_history)

                chart = (
                    alt.Chart(data)
                    .mark_line()
                    .encode(
                        x="window_end",
                        y=alt.Y(
                            "price_in_USD",
                            scale=alt.Scale(domain=[domain_start, domain_end]),
                        ),
                    )
                    .transform_window(
                        rank="rank()",
                        sort=[alt.SortField("window_end", order="descending")],
                    )
                    .transform_filter((alt.datum.rank < 20))
                )
                st.spinner("Simulation running...")
                st.altair_chart(chart, theme=None, use_container_width=True)
        except KeyboardInterrupt:
            print("Canceled by user.")
            consumer.close()

        if message_count == 80:
            my_slot1.markdown(
                """
:green[Simulation complete. Refresh the page to replay.]"""
            )

        # We create the placeholder once


placeholder = st.empty()


st.subheader(
    "What's going on behind the scenes of this chart?",
    divider="rainbow",
)
st.image(
    "./graph.png",
    caption="chart graphing relationship of different nodes in the data pipeline",
)
st.markdown(
    "First, data is piped from the [Alpaca API](https://docs.alpaca.markets/docs/getting-started) websocket into an Apache Kafka® topic located in Confluent Cloud. Next, the data is processed in [Confluent Cloud’s](https://confluent.cloud/) Flink SQL workspace with a query like this."
)
st.code(
    """INSERT INTO tumble_interval
SELECT symbol, DATE_FORMAT(window_start,'yyyy-MM-dd hh:mm:ss.SSS'), DATE_FORMAT(window_end,'yyyy-MM-dd hh:mm:ss.SSS'), AVG(price)
FROM TABLE(
        TUMBLE(TABLE SPY, DESCRIPTOR($rowtime), INTERVAL '5' SECONDS))
GROUP BY
    symbol,
    window_start,
    window_end;
""",
    language="python",
)
st.markdown(
    "Then, the data is consumed from a Kafka topic behind the FlinkSQL table in Confluent Cloud, and visualized using Streamlit."
)
st.markdown(
    "For more background on this project and to run it for yourself, visit the [GitHub repository](https://github.com/Cerchie/alpaca-kafka-flink-streamlit/tree/main)."
)
st.markdown(
    "Note: the Kafka consumer for this project reads from a specific offset created on Apr 1, '24. The data for this simulation is real but not live. To create your own live app, follow the instructions [here](https://github.com/Cerchie/alpaca-kafka-flink-streamlit?tab=readme-ov-file#how-to-use-flinksql-with-kafka-streamlit-and-the-alpaca-api). "
)

asyncio.run(main())
