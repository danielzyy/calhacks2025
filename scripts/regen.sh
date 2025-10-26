cd hcp_sdk

python hcp_sdk_gen.py --input examples/robot_arm.json --output ./out --host 127.0.0.1 --port 9000
python hcp_sdk_gen.py --input ../actuator/config/robot_arm.json --output ../actuator/gen --host 127.0.0.1 --port 9000

python hcp_sdk_gen.py --input examples/opencv_camera.json --output ./out --host 127.0.0.1 --port 9000

cd ..
