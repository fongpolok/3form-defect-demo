// Jacobian-based (damped least squares) inverse kinematics for the UR5e.
//
// See the write-up in the chat / project notes for the full explanation;
// short version:
//   1. Forward kinematics is "free" here — three.js's own scene graph
//      (URDFRobot from urdf-loader) already computes every joint/link's
//      world position and orientation once you call updateMatrixWorld().
//   2. The geometric Jacobian for an all-revolute chain (UR5e is 6
//      revolute joints) has a simple closed form per joint i:
//        linear part  J_v,i = z_i x (p_e - p_i)
//        angular part J_w,i = z_i
//      where z_i is joint i's current world-frame rotation axis, p_i its
//      world position, and p_e the end-effector's world position.
//   3. Inverse kinematics = walk downhill: measure the pose error between
//      where the tool currently is and where we want it, use the Jacobian
//      to find which joint nudges close that error fastest, take a damped
//      step (plain pseudo-inverse blows up near singularities — a fully
//      stretched elbow, wrist axes lining up — so a small damping term is
//      added, the standard Levenberg-Marquardt-style trick), and repeat.
import * as THREE from "three";
import { addScaledIdentity, matMul, matVecMul, solveLinearSystem, transpose } from "./linalg";

export const UR5E_END_EFFECTOR_LINK = "wrist_3_link";

export interface IKResult {
  anglesRad: number[];
  converged: boolean;
  iterations: number;
  positionErrorM: number;
  orientationErrorRad: number;
}

function getJointWorldAxis(joint: THREE.Object3D): THREE.Vector3 {
  // Every UR5e joint in ur5e.urdf rotates about its own local Z — see
  // <axis xyz="0 0 1"/> on each joint. Its *current* world-frame spin
  // axis is that local Z carried through the joint's own accumulated
  // world rotation (rotating about your own axis doesn't move that axis,
  // so this is exact, not an approximation).
  const q = new THREE.Quaternion();
  joint.getWorldQuaternion(q);
  return new THREE.Vector3(0, 0, 1).applyQuaternion(q).normalize();
}

function getWorldPosition(obj: THREE.Object3D): THREE.Vector3 {
  const p = new THREE.Vector3();
  obj.getWorldPosition(p);
  return p;
}

/** The 6xN geometric Jacobian: rows [dx,dy,dz, dwx,dwy,dwz] per unit joint velocity, one column per joint. */
export function computeGeometricJacobian(robot: any, jointNames: string[], endEffectorLinkName: string): number[][] {
  const endEffector = robot.links[endEffectorLinkName];
  const pe = getWorldPosition(endEffector);

  const J: number[][] = Array.from({ length: 6 }, () => new Array(jointNames.length).fill(0));
  jointNames.forEach((name, col) => {
    const joint = robot.joints[name];
    const zi = getJointWorldAxis(joint);
    const pi = getWorldPosition(joint);
    const jv = zi.clone().cross(pe.clone().sub(pi)); // linear velocity contribution
    J[0][col] = jv.x;
    J[1][col] = jv.y;
    J[2][col] = jv.z;
    J[3][col] = zi.x; // angular velocity contribution
    J[4][col] = zi.y;
    J[5][col] = zi.z;
  });
  return J;
}

/** Converts a small rotation (as a quaternion) into an angle*axis vector — the standard SO(3) "log map". */
function quaternionToRotationVector(q: THREE.Quaternion): THREE.Vector3 {
  const qn = q.clone().normalize();
  if (qn.w < 0) {
    qn.x *= -1;
    qn.y *= -1;
    qn.z *= -1;
    qn.w *= -1; // take the shorter of the two equivalent rotations
  }
  const angle = 2 * Math.acos(THREE.MathUtils.clamp(qn.w, -1, 1));
  const s = Math.sqrt(Math.max(1 - qn.w * qn.w, 1e-12));
  if (s < 1e-6) return new THREE.Vector3(0, 0, 0);
  return new THREE.Vector3(qn.x / s, qn.y / s, qn.z / s).multiplyScalar(angle);
}

export interface IKOptions {
  maxIterations?: number;
  dampingLambda?: number; // bigger = more stable near singularities, slower to converge
  stepScale?: number;
  posToleranceM?: number;
  oriToleranceRad?: number;
}

/**
 * Damped-least-squares IK: iteratively nudges `seedAnglesRad` until the
 * chain's end effector reaches `targetPosition`/`targetQuaternion` (world
 * frame, same units as the robot's own — meters, matching the URDF).
 * Mutates `robot`'s joint values as a side effect (this is how three.js/
 * urdf-loader forward kinematics works — set values, read back matrixWorld).
 */
export function solveIK(
  robot: any,
  jointNames: string[],
  endEffectorLinkName: string,
  targetPosition: THREE.Vector3,
  targetQuaternion: THREE.Quaternion,
  seedAnglesRad: number[],
  opts: IKOptions = {},
): IKResult {
  const maxIterations = opts.maxIterations ?? 150;
  const lambda = opts.dampingLambda ?? 0.03;
  const stepScale = opts.stepScale ?? 1.0;
  const posTol = opts.posToleranceM ?? 0.001; // 1mm
  const oriTol = opts.oriToleranceRad ?? 0.01; // ~0.6 deg

  let angles = [...seedAnglesRad];
  const endEffector = robot.links[endEffectorLinkName];

  let iter = 0;
  let posErr = Infinity;
  let oriErr = Infinity;
  for (; iter < maxIterations; iter++) {
    jointNames.forEach((name, i) => robot.setJointValue(name, angles[i]));
    robot.updateMatrixWorld(true);

    const currentPos = getWorldPosition(endEffector);
    const currentQuat = new THREE.Quaternion();
    endEffector.getWorldQuaternion(currentQuat);

    const ev = targetPosition.clone().sub(currentPos);
    const qErr = targetQuaternion.clone().multiply(currentQuat.clone().invert());
    const ew = quaternionToRotationVector(qErr);

    posErr = ev.length();
    oriErr = ew.length();
    if (posErr < posTol && oriErr < oriTol) break;

    const e = [ev.x, ev.y, ev.z, ew.x, ew.y, ew.z];
    const J = computeGeometricJacobian(robot, jointNames, endEffectorLinkName);
    const Jt = transpose(J);
    const JJt = matMul(J, Jt);
    const damped = addScaledIdentity(JJt, lambda * lambda); // (J J^T + lambda^2 I)
    const x = solveLinearSystem(damped, e);
    const deltaTheta = matVecMul(Jt, x).map((d) => THREE.MathUtils.clamp(d * stepScale, -0.3, 0.3));

    angles = angles.map((a, i) => a + deltaTheta[i]);
  }

  return {
    anglesRad: angles,
    converged: posErr < posTol && oriErr < oriTol,
    iterations: iter,
    positionErrorM: posErr,
    orientationErrorRad: oriErr,
  };
}

/** Builds a target orientation whose local Z axis points along `approachDirection` (e.g. -surfaceNormal). */
export function orientationFromApproach(approachDirection: THREE.Vector3): THREE.Quaternion {
  const zAxis = approachDirection.clone().normalize();
  const worldUpHint = Math.abs(zAxis.dot(new THREE.Vector3(0, 1, 0))) > 0.9
    ? new THREE.Vector3(1, 0, 0)
    : new THREE.Vector3(0, 1, 0);
  const xAxis = new THREE.Vector3().crossVectors(worldUpHint, zAxis).normalize();
  const yAxis = new THREE.Vector3().crossVectors(zAxis, xAxis).normalize();
  const m = new THREE.Matrix4().makeBasis(xAxis, yAxis, zAxis);
  return new THREE.Quaternion().setFromRotationMatrix(m);
}
