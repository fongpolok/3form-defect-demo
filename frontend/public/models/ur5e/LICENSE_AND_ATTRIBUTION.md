# UR5e 3D model — attribution

The 7 `.dae` mesh files in `visual/` and the kinematic parameters used to
build `ur5e.urdf` in this folder come from the **ROS-Industrial**
`universal_robot` package:

- Source: https://github.com/ros-industrial/universal_robot (`noetic-devel` branch)
- Package: `ur_description`
- License: **BSD** (per `ur_description/package.xml`'s `<license>BSD</license>` —
  the UR5e mesh set is not among the small set of newer robot models (ur15,
  ur18, ur20, ur30, ur8long) that carry Universal Robots A/S's own separate,
  more restrictive "Terms and Conditions for Use of Graphical Documentation";
  checked directly against that package.xml on 2026-08-27.)
- Downloaded/verified: 2026-08-27

`ur5e.urdf` in this folder is a hand-flattened URDF (visual geometry only,
no collision/inertial) built by this project from that package's
`config/ur5e/default_kinematics.yaml`, `physical_parameters.yaml`, and
`visual_parameters.yaml`, and its `urdf/inc/ur_macro.xacro` structure — not
estimated or approximated. It is not an official Universal Robots or
ROS-Industrial file.

If Universal Robots' own official CAD (STEP files, or their official URDF/
mesh export) becomes available, swap the files in `visual/` and update the
joint origins in `ur5e.urdf` to match — the rest of the viewer
(`frontend/src/components/Robot3DViewer.tsx`) doesn't need to change.
