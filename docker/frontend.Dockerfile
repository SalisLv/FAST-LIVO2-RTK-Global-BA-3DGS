FROM bag-to-3dgs-ros-dev:local
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
WORKDIR /gunda_ws
COPY FAST-LIVO2-RTK /gunda_ws/src/FAST-LIVO2-RTK
COPY gnss_comm /gunda_ws/src/gnss_comm
RUN ln -s /opt/rpg_vikit /gunda_ws/src/rpg_vikit \
    && source /opt/ros/noetic/setup.bash \
    && catkin_make -j1 -l2 -DCMAKE_BUILD_TYPE=Release \
    && mkdir -p /gunda_ws/src/FAST-LIVO2-RTK/Log/{pcd,result,image}
