"""Repository."""
import json
import logging
from abc import ABC, abstractmethod
from functools import cached_property
from typing import Any, Dict, Generic, List, Optional, Type

import pandas as pd

from blueetl.cache import CacheManager
from blueetl.config.simulations import SimulationsConfig
from blueetl.constants import CIRCUIT_ID, SIMULATION_ID, SIMULATION_PATH
from blueetl.extract.base import ExtractorT
from blueetl.extract.neuron_classes import NeuronClasses
from blueetl.extract.neurons import Neurons
from blueetl.extract.simulations import Simulations
from blueetl.extract.spikes import Spikes
from blueetl.extract.trial_steps import TrialSteps
from blueetl.extract.windows import Windows
from blueetl.utils import timed_log

L = logging.getLogger(__name__)


class BaseExtractor(ABC, Generic[ExtractorT]):
    """BaseExtractor class."""

    def __init__(self, repo: "Repository") -> None:
        """Initialize the object."""
        self._repo = repo

    @abstractmethod
    def extract_new(self) -> ExtractorT:
        """Instantiate an object from the configuration."""

    @abstractmethod
    def extract_cached(self, df: pd.DataFrame) -> ExtractorT:
        """Instantiate an object from a cached DataFrame."""

    def extract(self, name: str) -> ExtractorT:
        """Return an object extracted from the cache or as new.

        Args:
            name: name of the dataframe.
        """
        t_log = timed_log(L.info)
        is_new = is_modified = False
        df = self._repo.cache_manager.load_repo(name)
        if df is not None:
            initial_len = len(df)
            instance = self.extract_cached(df)
            is_modified = initial_len != len(instance.df)
        else:
            instance = self.extract_new()
            is_new = True
        assert instance is not None, "The extraction didn't return a valid instance."
        if is_new or is_modified:
            self._repo.cache_manager.dump_repo(df=instance.to_pandas(), name=name)
        t_log("Extracted %s: cached=%s, modified=%s", name, not is_new, is_modified)
        return instance


class SimulationsExtractor(BaseExtractor[Simulations]):
    """SimulationsExtractor class."""

    def extract_new(self) -> Simulations:
        """Instantiate an object from the configuration."""
        return Simulations.from_config(
            config=self._repo.simulations_config,
            query=self._repo.simulations_filter,
        )

    def extract_cached(self, df: pd.DataFrame) -> Simulations:
        """Instantiate an object from a cached DataFrame."""
        return Simulations.from_pandas(df, query=self._repo.simulations_filter)


class NeuronsExtractor(BaseExtractor[Neurons]):
    """NeuronsExtractor class."""

    def extract_new(self) -> Neurons:
        """Instantiate an object from the configuration."""
        return Neurons.from_simulations(
            simulations=self._repo.simulations,
            target=self._repo.extraction_config["target"],
            neuron_classes=self._repo.extraction_config["neuron_classes"],
            limit=self._repo.extraction_config["limit"],
        )

    def extract_cached(self, df: pd.DataFrame) -> Neurons:
        """Instantiate an object from a cached DataFrame."""
        query = {}
        if self._repo.simulations_filter:
            selected_sims = self._repo.simulations.df.etl.q(simulation_id=self._repo.simulation_ids)
            query = {CIRCUIT_ID: sorted(set(selected_sims[CIRCUIT_ID]))}
        return Neurons.from_pandas(df, query=query)


class NeuronClassesExtractor(BaseExtractor[NeuronClasses]):
    """NeuronClassesExtractor class."""

    def extract_new(self) -> NeuronClasses:
        """Instantiate an object from the configuration."""
        return NeuronClasses.from_neurons(
            neurons=self._repo.neurons,
            target=self._repo.extraction_config["target"],
            neuron_classes=self._repo.extraction_config["neuron_classes"],
            limit=self._repo.extraction_config["limit"],
        )

    def extract_cached(self, df: pd.DataFrame) -> NeuronClasses:
        """Instantiate an object from a cached DataFrame."""
        query = {}
        if self._repo.simulations_filter:
            selected_sims = self._repo.simulations.df.etl.q(simulation_id=self._repo.simulation_ids)
            query = {CIRCUIT_ID: sorted(set(selected_sims[CIRCUIT_ID]))}
        return NeuronClasses.from_pandas(df, query=query)


class TrialStepsExtractor(BaseExtractor[TrialSteps]):
    """TrialStepsExtractor class."""

    def extract_new(self) -> TrialSteps:
        """Instantiate an object from the configuration."""
        return TrialSteps.from_simulations(
            simulations=self._repo.simulations,
            config=self._repo.extraction_config,
        )

    def extract_cached(self, df: pd.DataFrame) -> TrialSteps:
        """Instantiate an object from a cached DataFrame."""
        query = {}
        if self._repo.simulations_filter:
            query = {SIMULATION_ID: self._repo.simulation_ids}
        return TrialSteps.from_pandas(df, query=query)


class WindowsExtractor(BaseExtractor[Windows]):
    """WindowsExtractor class."""

    def extract_new(self) -> Windows:
        """Instantiate an object from the configuration."""
        return Windows.from_simulations(
            simulations=self._repo.simulations,
            trial_steps=self._repo.trial_steps,
            config=self._repo.extraction_config,
        )

    def extract_cached(self, df: pd.DataFrame) -> Windows:
        """Instantiate an object from a cached DataFrame."""
        query = {}
        if self._repo.simulations_filter:
            query = {SIMULATION_ID: self._repo.simulation_ids}
        return Windows.from_pandas(df, query=query)


class SpikesExtractor(BaseExtractor[Spikes]):
    """SpikesExtractor class."""

    def extract_new(self) -> Spikes:
        """Instantiate an object from the configuration."""
        return Spikes.from_simulations(
            simulations=self._repo.simulations,
            neurons=self._repo.neurons,
            windows=self._repo.windows,
        )

    def extract_cached(self, df: pd.DataFrame) -> Spikes:
        """Instantiate an object from a cached DataFrame."""
        query = {}
        if self._repo.simulations_filter:
            query = {SIMULATION_ID: self._repo.simulation_ids}
        return Spikes.from_pandas(df, query=query)


class Repository:
    """Repository class."""

    def __init__(
        self,
        simulations_config: SimulationsConfig,
        extraction_config: Dict[str, Any],
        cache_manager: CacheManager,
        simulations_filter: Optional[Dict[str, Any]] = None,
        _dataframes: Optional[Dict[str, pd.DataFrame]] = None,
    ) -> None:
        """Initialize the repository.

        Args:
            simulations_config: simulation campaign configuration.
            extraction_config: extraction configuration.
            cache_manager: cache manager responsible to load and dump dataframes.
            simulations_filter: optional simulations filter.
            _dataframes: DataFrames to be automatically loaded, only for internal use.
        """
        self._extraction_config = extraction_config
        self._simulations_config = simulations_config
        self._cache_manager = cache_manager
        self._simulations_filter = simulations_filter
        self._mapping: Dict[str, Type[BaseExtractor]] = {
            "simulations": SimulationsExtractor,
            "neurons": NeuronsExtractor,
            "neuron_classes": NeuronClassesExtractor,
            "trial_steps": TrialStepsExtractor,
            "windows": WindowsExtractor,
            "spikes": SpikesExtractor,
        }
        self._names = list(self._mapping)
        if _dataframes:
            self._assign_from_dataframes(_dataframes)

    def __getstate__(self) -> Dict:
        """Get the object state when the object is pickled."""
        if not self.is_extracted():
            # ensure that the dataframes are extracted and stored to disk,
            # because we want to be able to use the cached data in the subprocesses.
            L.info("Extracting dataframes before serialization")
            self.extract()
        # Copy the object's state, excluding the unpicklable entries.
        names_set = set(self.names)
        return {k: v for k, v in self.__dict__.items() if k not in names_set}

    def __setstate__(self, state: Dict) -> None:
        """Set the object state when the object is unpickled."""
        self.__dict__.update(state)

    @property
    def extraction_config(self) -> Dict[str, Any]:
        """Access to the extraction configuration."""
        return self._extraction_config

    @property
    def simulations_config(self) -> SimulationsConfig:
        """Access to the simulation campaign configuration."""
        return self._simulations_config

    @property
    def cache_manager(self) -> CacheManager:
        """Access to the cache manager."""
        return self._cache_manager

    @property
    def simulations_filter(self) -> Optional[Dict[str, Any]]:
        """Access to the simulations filter."""
        return self._simulations_filter

    @property
    def names(self) -> List[str]:
        """Return the list of names of the extracted objects."""
        return self._names

    @cached_property
    def simulations(self) -> Simulations:
        """Return the Simulations extraction."""
        return self._mapping["simulations"](self).extract(name="simulations")

    @cached_property
    def neurons(self) -> Neurons:
        """Return the Neurons extraction."""
        return self._mapping["neurons"](self).extract(name="neurons")

    @cached_property
    def neuron_classes(self) -> NeuronClasses:
        """Return the NeuronClasses extraction."""
        return self._mapping["neuron_classes"](self).extract(name="neuron_classes")

    @cached_property
    def trial_steps(self) -> TrialSteps:
        """Return the TrialSteps extraction."""
        return self._mapping["trial_steps"](self).extract(name="trial_steps")

    @cached_property
    def windows(self) -> Windows:
        """Return the Windows extraction."""
        return self._mapping["windows"](self).extract(name="windows")

    @cached_property
    def spikes(self) -> Spikes:
        """Return the Spikes extraction."""
        return self._mapping["spikes"](self).extract(name="spikes")

    @property
    def simulation_ids(self) -> List[int]:
        """Return the list of simulation ids, possibly filtered."""
        return self.simulations.df[SIMULATION_ID].to_list()

    def extract(self) -> None:
        """Extract all the dataframes."""
        for name in self.names:
            getattr(self, name)
        self.check_extractions()

    def is_extracted(self) -> bool:
        """Return True if all the dataframes have been extracted."""
        # note: the cached_property is stored as an attribute after it's accessed
        return all(name in self.__dict__ for name in self.names)

    def check_extractions(self) -> None:
        """Check that all the dataframes have been extracted."""
        if not self.is_extracted():
            raise RuntimeError("Not all the dataframes have been extracted")

    def missing_simulations(self) -> pd.DataFrame:
        """Return a DataFrame with the simulations ignored because of missing spikes.

        Returns:
            pd.DataFrame with simulation_path as columns, simulation conditions as index,
                and one record for each ignored and missing simulation.
        """
        all_simulations = self._simulations_config.to_pandas().rename(SIMULATION_PATH)
        extracted_simulations = self.simulations.df[SIMULATION_PATH]
        return (
            pd.merge(
                all_simulations,
                extracted_simulations,
                left_on=[*all_simulations.index.names, SIMULATION_PATH],
                right_on=[*extracted_simulations.index.names, SIMULATION_PATH],
                how="left",
                indicator=True,
            )
            .etl.q(_merge="left_only")
            .drop(columns="_merge")
        )

    def _print(self) -> None:
        """Print some information about the instance.

        Only for debug and internal use, it may be removed in a future release.
        """
        print("### extraction_config")
        print(json.dumps(self._extraction_config, indent=2))
        print("### simulations_config")
        print(json.dumps(self._simulations_config.to_dict(), indent=2))
        for name in self.names:
            print(f"### {name}.df")
            df = getattr(getattr(self, name), "df")
            print(df)
            print(df.dtypes)

    def _assign_from_dataframes(self, dicts: Dict[str, pd.DataFrame]) -> None:
        """Assign the repository properties from the given dict of DataFrames."""
        for name, df in dicts.items():
            assert name not in self.__dict__
            value = self._mapping[name](self).extract_cached(df)
            setattr(self, name, value)

    def apply_filter(self, simulations_filter: Dict[str, Any]) -> "Repository":
        """Apply the given filter and return a new object.

        Filtered dataframes are not written to disk.
        """
        dataframes = {name: getattr(self, name).df for name in self.names}
        return Repository(
            simulations_config=self._simulations_config,
            extraction_config=self._extraction_config,
            cache_manager=self.cache_manager.to_readonly(),
            simulations_filter=simulations_filter,
            _dataframes=dataframes,
        )