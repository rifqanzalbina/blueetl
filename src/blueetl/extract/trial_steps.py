"""TrialSteps extractor."""
import logging
from typing import Dict, Optional

import numpy as np
import pandas as pd
from bluepy import Circuit, Simulation

from blueetl.config.analysis_model import TrialStepsConfig
from blueetl.constants import CIRCUIT_ID, SIMULATION_ID, TRIAL_STEPS_LABEL, TRIAL_STEPS_VALUE
from blueetl.extract.base import BaseExtractor
from blueetl.extract.simulations import Simulations
from blueetl.utils import import_by_string, timed

L = logging.getLogger(__name__)


class TrialSteps(BaseExtractor):
    """TrialSteps extractor class."""

    COLUMNS = [SIMULATION_ID, CIRCUIT_ID, TRIAL_STEPS_LABEL, TRIAL_STEPS_VALUE]
    # allow additional columns that can be used to store more details
    _allow_extra_columns = True
    # trial_steps are optional
    _allow_empty_data = True

    @classmethod
    def _load_spikes(
        cls,
        simulation: Simulation,
        circuit: Circuit,
        target: Optional[str],
        limit: Optional[int],
        initial_offset: float,
        t_start: float,
        t_end: float,
    ) -> np.ndarray:
        # circuit is passed explicitly instead of loading it from simulation.circuit
        # to take advantage of any circuit already loaded in memory
        with timed(L.info, "Cells loaded from circuit"):
            cells_group = {"$target": target} if target else None
            gids = circuit.cells.get(group=cells_group, properties=[]).index.to_numpy()
        neuron_count = len(gids)
        if limit and neuron_count > limit:
            gids = np.random.choice(gids, size=limit, replace=False)
        L.info("Selected %s/%s gids", len(gids), neuron_count)
        spikes = simulation.spikes.get(
            gids, t_start=initial_offset + t_start, t_end=initial_offset + t_end
        ).index.to_numpy()
        spikes -= initial_offset
        L.info("Selected %s spikes", len(spikes))
        return spikes

    @classmethod
    def from_simulations(
        cls,
        simulations: Simulations,
        trial_steps_config: Dict[str, TrialStepsConfig],
        target: Optional[str],
        limit: Optional[int],
    ) -> "TrialSteps":
        """Return a new TrialSteps instance from the given simulations and configuration.

        Args:
            simulations: Simulations extractor.
            trial_steps_config: configuration dict.
            target: optional target.
            limit: optional limit of neurons to consider.

        Returns:
            TrialSteps: new instance.
        """
        # pylint: disable=too-many-locals
        results = []
        for trial_steps_label, trial_steps_params in trial_steps_config.items():
            func = import_by_string(trial_steps_params.function)
            t_start, t_end = trial_steps_params.bounds
            initial_offset = trial_steps_params.initial_offset
            for _, rec in simulations.df.etl.iter():
                L.info(
                    "Processing trial_steps_label=%s, simulation_id=%s, circuit_id=%s",
                    trial_steps_label,
                    rec.simulation_id,
                    rec.circuit_id,
                )
                spikes = cls._load_spikes(
                    simulation=rec.simulation,
                    circuit=rec.circuit,
                    target=target,
                    limit=limit,
                    initial_offset=initial_offset,
                    t_start=t_start,
                    t_end=t_end,
                )
                trial_steps_result = func(spikes, trial_steps_params.dict())
                try:
                    trial_steps_value = trial_steps_result.pop(TRIAL_STEPS_VALUE)
                except KeyError:
                    L.error(
                        "The dictionary returned by %r must contain the %r key",
                        trial_steps_params.function,
                        TRIAL_STEPS_VALUE,
                    )
                    raise
                L.info("trial_steps_value=%s", trial_steps_value)
                results.append(
                    {
                        SIMULATION_ID: rec.simulation_id,
                        CIRCUIT_ID: rec.circuit_id,
                        TRIAL_STEPS_LABEL: trial_steps_label,
                        TRIAL_STEPS_VALUE: trial_steps_value,
                        **trial_steps_result,
                    }
                )
        df = pd.DataFrame(results) if results else pd.DataFrame([], columns=cls.COLUMNS)
        return cls(df)
