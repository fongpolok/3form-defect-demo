// Shared between Robot3DViewer (pendant) and CadPathRobotViewer (CAD path
// motion preview) so both load the exact same real UR5e model/joint chain.
export const UR5E_URDF_URL = "/models/ur5e/ur5e.urdf";
export const UR5E_JOINT_NAMES = [
  "shoulder_pan_joint",
  "shoulder_lift_joint",
  "elbow_joint",
  "wrist_1_joint",
  "wrist_2_joint",
  "wrist_3_joint",
];
