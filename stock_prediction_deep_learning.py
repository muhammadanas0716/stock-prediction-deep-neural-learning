# Copyright 2020 Jordi Corbilla. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================
import os
import secrets
import pandas as pd
import tensorflow as tf
from sklearn.preprocessing import MinMaxScaler
import datetime
import numpy as np
import yfinance as yf

from stock_prediction_lstm import LongShortTermMemory
from stock_prediction_plotter import Plotter
os.environ["PATH"] += os.pathsep + 'C:/Program Files (x86)/Graphviz2.38/bin/'


def data_verification(train):
    print('mean:', train.mean(axis=0))
    print('max', train.max())
    print('min', train.min())
    print('Std dev:', train.std(axis=0))

def load_data_transform(time_steps, min_max, training_data, test_data):
    train_scaled = min_max.fit_transform(training_data)
    data_verification(train_scaled)

    # Training Data Transformation
    x_train = []
    y_train = []
    for i in range(time_steps, train_scaled.shape[0]):
        x_train.append(train_scaled[i - time_steps:i])
        y_train.append(train_scaled[i, 0])

    x_train, y_train = np.array(x_train), np.array(y_train)
    x_train = np.reshape(x_train, (x_train.shape[0], x_train.shape[1], 1))

    total_data = pd.concat((training_data, test_data), axis=0)
    inputs = total_data[len(total_data) - len(test_data) - time_steps:]
    test_scaled = min_max.fit_transform(inputs)

    # Testing Data Transformation
    x_test = []
    y_test = []
    for i in range(time_steps, test_scaled.shape[0]):
        x_test.append(test_scaled[i - time_steps:i])
        y_test.append(test_scaled[i, 0])

    x_test, y_test = np.array(x_test), np.array(y_test)
    x_test = np.reshape(x_test, (x_test.shape[0], x_test.shape[1], 1))
    return (x_train, y_train), (x_test, y_test)


def train_LSTM_network(start_date, ticker, validation_date):
    min_max = MinMaxScaler(feature_range=(0, 1))
    sec = yf.Ticker(ticker)
    data = yf.download([ticker], start=start_date, end=datetime.date.today())[['Close']]
    data = data.reset_index()
    print(data)

    plotter = Plotter(True, project_folder, sec.info['shortName'], sec.info['currency'], stock_ticker)

    training_data = data[data['Date'] < validation_date].copy()
    test_data = data[data['Date'] >= validation_date].copy()
    training_data = training_data.set_index('Date')
    test_data = test_data.set_index('Date')
    plotter.plot_histogram_data_split(training_data, test_data, validation_date)

    (x_train, y_train), (x_test, y_test) = load_data_transform(60, min_max, training_data, test_data)

    lstm = LongShortTermMemory(project_folder)
    model = lstm.create_model(x_train)

    defined_metrics = [
        tf.keras.metrics.MeanSquaredError(name='MSE')
    ]

    callback = tf.keras.callbacks.EarlyStopping(monitor='val_loss', patience=3, mode='min', verbose=1)

    model.compile(optimizer='adam', loss='mean_squared_error', metrics=defined_metrics)
    history = model.fit(x_train, y_train, epochs=epochs, batch_size=batch_size, validation_data=(x_test, y_test),
                        callbacks=[callback])
    print("saving weights")
    model.save(os.path.join(project_folder, 'model_weights.h5'))
    plotter.plot_loss(history)
    plotter.plot_mse(history)

    print("display the content of the model")
    baseline_results = model.evaluate(x_test, y_test, verbose=2)
    for name, value in zip(model.metrics_names, baseline_results):
        print(name, ': ', value)
    print()

    print("plotting prediction results")
    test_predictions_baseline = model.predict(x_test)
    test_predictions_baseline = min_max.inverse_transform(test_predictions_baseline)
    test_predictions_baseline = pd.DataFrame(test_predictions_baseline)
    test_predictions_baseline.to_csv(os.path.join(project_folder, 'predictions.csv'))

    test_predictions_baseline.rename(columns={0: stock_ticker + '_predicted'}, inplace=True)
    test_predictions_baseline = test_predictions_baseline.round(decimals=0)
    test_predictions_baseline.index = test_data.index
    plotter.project_plot_predictions(test_predictions_baseline, test_data)

    print("prediction is finished")


if __name__ == '__main__':
    stock_start_date = pd.to_datetime('2004-08-01')
    stock_ticker = 'GOOG'
    epochs = 100
    batch_size = 32
    token = secrets.token_hex(16)
    project_folder = os.path.join(os.getcwd(), token)
    if not os.path.exists(project_folder):
        os.makedirs(project_folder)
    stock_validation_date = pd.to_datetime('2017-01-01')
    train_LSTM_network(stock_start_date, stock_ticker, stock_validation_date)
