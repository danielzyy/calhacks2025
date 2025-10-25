import pytest
from actuator.arm_kinematics import *

def test_mech_to_dh_and_back():
    """Test conversion between mech and DH angles."""
    mech_angles = np.array([0.0, np.pi/4, -np.pi/4, 0.0, 0.0])
    dh_angles = mech_to_dh_angles(mech_angles)
    mech_converted = dh_to_mech_angles(dh_angles)
    assert np.allclose(mech_angles, mech_converted), "Mech to DH conversion failed."