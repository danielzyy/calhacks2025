import hcp_executor

hcp = hcp_executor.HCPExecutor()

hcp.register_device("SoarM100", "6-DOF arm controller", port=5001)

hcp.register_action(
    "SoarM100",
    "move_to",
    "Move arm to XYZ coordinates",
    [("x", float), ("y", float), ("z", float)],
)

hcp.register_action(
    "SoarM100",
    "pincer",
    "Open or close the pincer",
    [("open", bool)],
)

hcp.execute_action("SoarM100", "move_to", {"x": 1.0, "y": 2.0, "z": 3.0})
