FROM ros:noetic-ros-base-focal
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
ENV DEBIAN_FRONTEND=noninteractive
RUN sed -i 's|http://archive.ubuntu.com/ubuntu|https://archive.ubuntu.com/ubuntu|g; s|http://security.ubuntu.com/ubuntu|https://security.ubuntu.com/ubuntu|g' /etc/apt/sources.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends build-essential cmake ca-certificates git \
       libeigen3-dev libopencv-dev libpcl-dev libboost-thread-dev libboost-timer-dev \
       libgeographic-dev libgoogle-glog-dev libtbb-dev pcl-tools ros-noetic-pcl-ros \
       ros-noetic-eigen-conversions ros-noetic-cv-bridge ros-noetic-image-transport \
       ros-noetic-compressed-image-transport ros-noetic-cmake-modules ros-noetic-rviz ros-noetic-rosbag \
    && rm -rf /var/lib/apt/lists/*
COPY .deps/Sophus /opt/Sophus
RUN sed -i 's/unit_complex_\.real() = 1\.;/unit_complex_.real(1.);/; s/unit_complex_\.imag() = 0\.;/unit_complex_.imag(0.);/' /opt/Sophus/sophus/so2.cpp \
    && cmake -S /opt/Sophus -B /tmp/sophus -DCMAKE_BUILD_TYPE=Release \
    && cmake --build /tmp/sophus -j2 && cmake --install /tmp/sophus
COPY .deps/rpg_vikit/vikit_common /opt/rpg_vikit/vikit_common
COPY .deps/rpg_vikit/vikit_ros /opt/rpg_vikit/vikit_ros
COPY .deps/gtsam /opt/gtsam
RUN cmake -S /opt/gtsam -B /tmp/gtsam -DCMAKE_BUILD_TYPE=Release \
      -DGTSAM_BUILD_WITH_MARCH_NATIVE=OFF -DGTSAM_USE_SYSTEM_EIGEN=ON \
      -DGTSAM_BUILD_TESTS=OFF -DGTSAM_BUILD_EXAMPLES_ALWAYS=OFF \
      -DGTSAM_BUILD_UNSTABLE=OFF -DGTSAM_BUILD_PYTHON=OFF \
    && cmake --build /tmp/gtsam -j1 && cmake --install /tmp/gtsam \
    && ldconfig && rm -rf /tmp/gtsam /tmp/sophus /opt/gtsam /opt/Sophus
