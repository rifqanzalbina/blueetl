"""Common constants."""
import numpy as np

GID = "gid"
TIME = "time"
SIMULATION_PATH = "simulation_path"
SIMULATION_ID = "simulation_id"
SIMULATION = "simulation"
CIRCUIT_ID = "circuit_id"
CIRCUIT = "circuit"
NEURON_CLASS = "neuron_class"
NEURON_CLASS_INDEX = "neuron_class_index"  # incremental gid index for each neuron class
WINDOW = "window"
TRIAL = "trial"
OFFSET = "offset"
T_START = "t_start"
T_STOP = "t_stop"
DURATION = "duration"
WINDOW_TYPE = "window_type"
COUNT = "count"
TRIAL_STEPS_LABEL = "trial_steps_label"
TRIAL_STEPS_VALUE = "trial_steps_value"
TIMES = "times"
BIN = "bin"

DTYPES = {
    GID: np.int64,
    TIME: np.float64,
    SIMULATION_ID: np.int16,
    CIRCUIT_ID: np.int16,
    NEURON_CLASS: "category",
    WINDOW: "category",
    TRIAL: np.int16,
    T_START: np.float64,
    T_STOP: np.float64,
    DURATION: np.float64,
}