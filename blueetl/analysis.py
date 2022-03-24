import logging
from collections import defaultdict

import pandas as pd

from blueetl.config.simulations import SimulationsConfig
from blueetl.repository import Repository
from blueetl.utils import import_by_string, timed

L = logging.getLogger(__name__)


class Analyzer:
    def __init__(self, analysis_config, use_cache=False):
        self.analysis_config = analysis_config
        self.repo = Repository(
            simulations_config=SimulationsConfig.load(analysis_config["simulation_campaign"]),
            extraction_config=analysis_config["extraction"],
            cache_dir=self.analysis_config["output"],
            use_cache=use_cache,
        )

    def initialize(self):
        self.repo.extract()
        self.repo.print()

    def calculate_features_by_gid(self):
        feature_collections = self.analysis_config["analysis"]["features"].get("gid", [])
        records = []
        if feature_collections:
            with timed(L.info, "Completed features_by_gid"):
                for key, df in self.repo.spikes.grouped_by_gid():
                    # key names: simulation_id, circuit_id, neuron_class, window, gid
                    # df columns: trial, time
                    record = key._asdict()
                    for feature_collection in feature_collections:
                        func = import_by_string(feature_collection["function"])
                        params = feature_collection.get("params", {})
                        record.update(func(repo=self.repo, key=key, df=df, params=params))
                    records.append(record)
        # in the returned df, the type of `neuron_class` and `window` is `object`
        return pd.DataFrame(records)

    def calculate_features_by_neuron_class(self):
        feature_collections = self.analysis_config["analysis"]["features"].get("neuron_class", [])
        records = []
        if feature_collections:
            with timed(L.info, "Completed features_by_neuron_class"):
                for key, df in self.repo.spikes.grouped_by_neuron_class():
                    # key names: simulation_id, circuit_id, neuron_class, window
                    # df columns: trial, gid, time
                    L.info("Calculating features_by_neuron_class for %s", key)
                    record = key._asdict()
                    for feature_collection in feature_collections:
                        func = import_by_string(feature_collection["function"])
                        params = feature_collection.get("params", {})
                        record.update(func(repo=self.repo, key=key, df=df, params=params))
                    records.append(record)
        # in the returned df, the type of `neuron_class` and `window` is `object`
        return pd.DataFrame(records)

    def calculate_generic_features(self):
        feature_collections = self.analysis_config["analysis"]["features"].get("generic", [])
        features_records = defaultdict(list)
        if feature_collections:
            func = import_by_string(feature_collections["function"])
            params = feature_collections.get("params", {})
            with timed(L.info, "Completed features"):
                for key, df in self.repo.spikes.grouped_by_neuron_class():
                    # key names: simulation_id, circuit_id, neuron_class, window
                    # df columns: trial, gid, time
                    L.info("Calculating features for %s", key)
                    record = key._asdict()
                    conditions = list(record.keys())
                    values = tuple(record.values())
                    features_dict = func(repo=self.repo, key=key, df=df, params=params)
                    for feature_group, result in features_dict.items():
                        assert isinstance(
                            result, pd.DataFrame
                        ), "The returned object must be a DataFrame"
                        # ignore the index if it's unnamed and with one level; this can be useful
                        # for example when the returned DataFrame has a useless RangeIndex
                        drop = result.index.names == [None]
                        result = result.etl.add_conditions(conditions, values, drop=drop)
                        features_records[feature_group].append(result)
        features = {
            feature_group: pd.concat(df_list) for feature_group, df_list in features_records.items()
        }
        return features
