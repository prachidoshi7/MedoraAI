import os
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
import tensorflow as tf

base_model = tf.keras.applications.MobileNetV2(
    input_shape=(128, 128, 3),
    include_top=False,
    weights=None,
)

# Build a dummy model to compute shapes
dummy_input = tf.keras.Input(shape=(128, 128, 3))
dummy_model = tf.keras.Model(inputs=base_model.input, outputs=base_model.output)

# Print last layers by spatial resolution
print("=== Last layer at each spatial resolution ===")
spatial_layers = {}
for layer in base_model.layers:
    try:
        out = layer.output
        if hasattr(out, 'shape') and len(out.shape) == 4:
            h = out.shape[1]
            w = out.shape[2]
            if h is not None and w is not None:
                key = f"{h}x{w}"
                spatial_layers[key] = (layer.name, out.shape)
    except Exception:
        pass

for key in sorted(spatial_layers.keys(), key=lambda x: int(x.split('x')[0]), reverse=True):
    name, shape = spatial_layers[key]
    print(f"  {key}: {name} -> {shape}")

print(f"\nFinal output: {base_model.output.shape}")
print(f"Last layer name: {base_model.layers[-1].name}")
