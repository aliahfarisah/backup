'''
Load nn model for infer
'''

import onnx
import os
import time

import onnxruntime as ort
import numpy as np

class ONNXModel:
    def __init__(self, model_path):
        # Load the ONNX model
        self.model = onnx.load(model_path)
        onnx.checker.check_model(self.model)  # Optional: to ensure the model is valid
        
        # Create an ONNX Runtime session
        self.session = ort.InferenceSession(model_path)

        # Get the input name and shape
        self.input_name = self.session.get_inputs()[0].name
        self.input_shape = self.session.get_inputs()[0].shape

    def check_input_dim(self, input_data):
        # Check if the input data has the same number of dimensions as the model input
        input_data_shape = input_data.shape
        if len(input_data_shape) != len(self.input_shape):
            raise ValueError(f"Input dimension mismatch. Expected: {len(self.input_shape)}, but got: {len(input_data_shape)}")
        
        for idx, dim in enumerate(self.input_shape):
            # Allow dynamic dimensions like None or symbolic dimensions like 'batch'
            if dim is not None and not isinstance(dim, str) and dim != input_data_shape[idx]:
                raise ValueError(f"Input size mismatch at dimension {idx}. Expected: {dim}, but got: {input_data_shape[idx]}")

    def infer(self, input_data):
        # Ensure the input data shape matches the model's input shape
        self.check_input_dim(input_data)
        
        # Perform inference
        input_dict = {self.input_name: input_data}
        result = self.session.run(None, input_dict)
        
        return result

# Example usage:
if __name__ == "__main__":
    model_folder = 'nn_models'
    model_path = r"C:\G7\rover\Rover_02_01.onnx"
    model = ONNXModel(os.path.join(model_folder, model_path))
    
    # Example input data (replace with actual input data)
    input_data = np.random.rand(1, 14).astype(np.float32)
    target_position = np.array([0.5, 0.03, -0.5]).astype(np.float32)
    transform_position = np.array([0.2, 0.03, 0.2]).astype(np.float32)
    transform_vel = np.array([0.001, 0.001]).astype(np.float32)
    boundary_min = np.array([-0.75, 0.0, -0.75]).astype(np.float32)
    boundary_max = np.array([0.75, 0.0, 0.75]).astype(np.float32)

    for i in range(10):
        input_array = np.concatenate((target_position, transform_position, transform_vel, boundary_min, boundary_max))
        # Transform to 2D array
        input_array = np.array([input_array])
        #print("Input data:", input_data)
        print("Input array:", input_array)
        
        # Measure inference time
        start_time = time.time()
        
        # Perform inference
        output = model.infer(input_array)
        #print("Output: ", model.model.graph.output)
        #print("Inference result:", output)
        cont_actions = output[2][0]
        print("Actions:", cont_actions)
        transform_position[0] += cont_actions[0]
        transform_position[2] += cont_actions[1]

        end_time = time.time()

        inference_time = end_time - start_time
        print(f"Inference time: {inference_time:.6f} seconds")
