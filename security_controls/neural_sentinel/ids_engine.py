import tensorflow as tf
from tensorflow.keras.models import Model
from tensorflow.keras.layers import Input, Dense, Dropout, LayerNormalization, MultiHeadAttention
from tensorflow.keras.optimizers import Adam
from tensorflow.keras.losses import BinaryCrossentropy
from tensorflow.keras.metrics import AUC, Precision, Recall
import numpy as np
import pandas as pd
from sklearn.preprocessing import RobustScaler
from sklearn.model_selection import train_test_split
import joblib
import warnings
warnings.filterwarnings('ignore')

class QuantumTransformerIDS:
    def __init__(self, input_shape=(42,), num_heads=6, ff_dim=128, num_layers=3, rate=0.1):
        self.input_shape = input_shape
        self.num_heads = num_heads
        self.ff_dim = ff_dim
        self.num_layers = num_layers
        self.rate = rate
        self.scaler = RobustScaler()
        self.threshold = 0.98  # High precision threshold
        self.model = self.build_quantum_transformer()
        self.adversarial_model = self.build_adversarial_detector()

    def transformer_encoder(self, inputs):
        # Self-attention layer
        attention_output = MultiHeadAttention(
            num_heads=self.num_heads, key_dim=self.input_shape[0])(inputs, inputs)
        attention_output = Dropout(self.rate)(attention_output)
        out1 = LayerNormalization(epsilon=1e-6)(inputs + attention_output)
        
        # Feed-forward network
        ffn_output = Dense(self.ff_dim, activation="gelu")(out1)
        ffn_output = Dense(self.input_shape[0])(ffn_output)
        ffn_output = Dropout(self.rate)(ffn_output)
        return LayerNormalization(epsilon=1e-6)(out1 + ffn_output)

    def build_quantum_transformer(self):
        inputs = Input(shape=self.input_shape)
        x = inputs
        
        # Stack multiple transformer layers
        for _ in range(self.num_layers):
            x = self.transformer_encoder(x)
        
        # Quantum-inspired dense layers
        x = Dense(256, activation="selu")(x)
        x = Dropout(0.3)(x)
        x = Dense(128, activation="selu")(x)
        x = Dropout(0.2)(x)
        outputs = Dense(1, activation="sigmoid")(x)
        
        # Custom optimizer with quantum annealing-like behavior
        optimizer = Adam(
            learning_rate=tf.keras.optimizers.schedules.ExponentialDecay(
                initial_learning_rate=1e-3,
                decay_steps=10000,
                decay_rate=0.9)
        )
        
        model = Model(inputs=inputs, outputs=outputs)
        model.compile(
            optimizer=optimizer,
            loss=BinaryCrossentropy(from_logits=False),
            metrics=[
                AUC(name='auc'),
                Precision(name='precision'),
                Recall(name='recall')
            ]
        )
        return model

    def build_adversarial_detector(self):
        # Separate model for detecting adversarial examples
        inputs = Input(shape=self.input_shape)
        x = Dense(64, activation="tanh")(inputs)
        x = Dense(32, activation="tanh")(x)
        outputs = Dense(1, activation="sigmoid")(x)
        
        model = Model(inputs=inputs, outputs=outputs)
        model.compile(
            optimizer="adam",
            loss="binary_crossentropy",
            metrics=["accuracy"]
        )
        return model

    def train(self, X, y, validation_split=0.2, epochs=100, batch_size=512):
        # Preprocess data
        X_scaled = self.scaler.fit_transform(X)
        X_train, X_val, y_train, y_val = train_test_split(
            X_scaled, y, test_size=validation_split, random_state=42
        )
        
        # Train main model
        history = self.model.fit(
            X_train, y_train,
            validation_data=(X_val, y_val),
            epochs=epochs,
            batch_size=batch_size,
            callbacks=[
                tf.keras.callbacks.EarlyStopping(
                    monitor='val_auc',
                    patience=5,
                    mode='max',
                    restore_best_weights=True
                ),
                tf.keras.callbacks.ReduceLROnPlateau(
                    monitor='val_loss',
                    factor=0.5,
                    patience=3,
                    min_lr=1e-6
                )
            ]
        )
        
        # Train adversarial detector
        adv_X = self.generate_adversarial_samples(X_train)
        adv_y = np.ones(len(adv_X))
        self.adversarial_model.fit(
            np.vstack([X_train, adv_X]),
            np.concatenate([np.zeros(len(X_train)), adv_y]),
            epochs=20,
            batch_size=256
        )
        
        # Save models and scaler
        self.model.save('quantum_transformer_ids.h5')
        self.adversarial_model.save('adversarial_detector.h5')
        joblib.dump(self.scaler, 'quantum_scaler.pkl')
        
        return history

    def generate_adversarial_samples(self, X, epsilon=0.1):
        # Fast Gradient Sign Method for adversarial training
        X_tensor = tf.convert_to_tensor(X, dtype=tf.float32)
        with tf.GradientTape() as tape:
            tape.watch(X_tensor)
            prediction = self.model(X_tensor)
            loss = BinaryCrossentropy()(
                tf.ones_like(prediction), prediction)
        gradient = tape.gradient(loss, X_tensor)
        perturbation = epsilon * tf.sign(gradient)
        return X + perturbation.numpy()

    def detect_anomalies(self, network_data):
        # Preprocess data
        data_scaled = self.scaler.transform(network_data)
        
        # Get predictions from both models
        main_pred = self.model.predict(data_scaled)
        adv_pred = self.adversarial_model.predict(data_scaled)
        
        # Combined anomaly score
        anomaly_scores = 0.7 * main_pred + 0.3 * adv_pred
        anomalies = anomaly_scores > self.threshold
        
        return {
            'anomalies': anomalies,
            'scores': anomaly_scores,
            'main_scores': main_pred,
            'adv_scores': adv_pred
        }

    def evaluate_attack(self, X_attack, y_attack):
        # Comprehensive attack evaluation
        data_scaled = self.scaler.transform(X_attack)
        eval_results = {}
        
        # Main model evaluation
        main_eval = self.model.evaluate(data_scaled, y_attack, verbose=0)
        eval_results['main_model'] = dict(zip(
            self.model.metrics_names, main_eval))
        
        # Adversarial model evaluation
        adv_pred = self.adversarial_model.predict(data_scaled)
        adv_accuracy = np.mean(
            (adv_pred > 0.5).astype(int) == y_attack)
        eval_results['adversarial_detector'] = {
            'accuracy': adv_accuracy,
            'avg_score': np.mean(adv_pred)
        }
        
        return eval_results
