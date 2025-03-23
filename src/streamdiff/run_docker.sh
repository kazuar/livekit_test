# Run docker nvidia/cuda:12.1.1-devel-ubuntu22.04 with bash and mount the current directory
docker run -it --gpus all --runtime nvidia -v $(pwd):/app nvidia/cuda:12.1.1-devel-ubuntu22.04 bash

