FROM pytorch/pytorch:2.8.0-cuda12.8-cudnn9-runtime
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl \
    && curl -fsSLo /tmp/cuda-keyring.deb https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.1-1_all.deb
RUN dpkg -i /tmp/cuda-keyring.deb \
    && sed -i 's|http://archive.ubuntu.com|https://archive.ubuntu.com|g; s|http://security.ubuntu.com|https://security.ubuntu.com|g' /etc/apt/sources.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends g++ ninja-build cuda-nvcc-12-8 cuda-cudart-dev-12-8 \
    && rm -rf /var/lib/apt/lists/* /tmp/cuda-keyring.deb
ENV CUDA_HOME=/usr/local/cuda-12.8
ENV PATH=/usr/local/cuda-12.8/bin:$PATH
ARG CUDA_ARCH_LIST=8.0;8.6;8.9;9.0;12.0
ENV TORCH_CUDA_ARCH_LIST=$CUDA_ARCH_LIST MAX_JOBS=2
RUN python -m pip install --no-cache-dir plyfile==1.1.5
