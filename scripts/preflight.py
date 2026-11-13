"""Validate the bag connections and return the camera transport and topic."""
import sys

import rosbag
import yaml

with open("/profile/frontend.yaml") as config_file:
    config = yaml.safe_load(config_file)

if not config["global_lvba"]["output_en"] or config["global_lvba"]["sequence_name"] != "pipeline":
    sys.exit("frontend.yaml must enable Global-LVBA export with sequence_name: pipeline")

if not all(config["common"].get(name) for name in ("img_en", "lidar_en")):
    sys.exit("This pipeline needs camera and LiDAR enabled in frontend.yaml")
if len(config["gps"].get("extrinsic_T", ())) != 3:
    sys.exit("Set the three IMU-to-GNSS antenna offsets in gps.extrinsic_T")

camera = config["common"]["img_topic"]
required = {
    config["common"]["lid_topic"]: {"livox_ros_driver/CustomMsg", "sensor_msgs/PointCloud2"},
    config["common"]["imu_topic"]: {"sensor_msgs/Imu"},
    config["gps"]["gps_topic"]: {"gnss_comm/GnssPVTSolnMsg"},
}
try:
    with rosbag.Bag("/input.bag", "r") as bag:
        topics = bag.get_type_and_topic_info().topics
except (rosbag.ROSBagException, OSError) as error:
    sys.exit(f"Cannot open indexed ROS 1 bag: {error}")

for topic, types in required.items():
    info = topics.get(topic)
    if info is None or info.message_count < 1:
        sys.exit(f"Bag is missing required data on {topic}")
    if info.msg_type not in types:
        sys.exit(f"{topic} has type {info.msg_type}; supported types: {', '.join(sorted(types))}")

if camera in topics and topics[camera].msg_type == "sensor_msgs/Image" and topics[camera].message_count:
    print("raw", camera)
elif (camera + "/compressed" in topics
      and topics[camera + "/compressed"].msg_type == "sensor_msgs/CompressedImage"
      and topics[camera + "/compressed"].message_count):
    print("compressed", camera)
else:
    sys.exit(f"Bag has no sensor_msgs/Image on {camera} or CompressedImage on {camera}/compressed")
