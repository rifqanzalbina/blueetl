"""Analysis Configuration Models."""
from pathlib import Path
from typing import Any, Optional, TypeVar, Union

from pydantic import BaseModel as PydanticBaseModel
from pydantic import Extra, Field, root_validator, validator

from blueetl.constants import CONFIG_VERSION
from blueetl.utils import checksum_str, dump_yaml, load_yaml

BaseModelT = TypeVar("BaseModelT", bound="BaseModel")


class BaseModel(PydanticBaseModel):
    """Custom BaseModel."""

    class Config:
        """Custom Model Config."""

        extra = Extra.forbid
        allow_mutation = True
        allow_inf_nan = False
        validate_assignment = True
        smart_union = True

    def dict(self, *args, by_alias=True, **kwargs):
        """Generate a dictionary representation of the model, using by_alias=True by default."""
        return super().dict(*args, by_alias=by_alias, **kwargs)

    def json(self, *args, by_alias=True, **kwargs):
        """Generate a JSON representation of the model, using by_alias=True by default."""
        return super().json(*args, by_alias=by_alias, **kwargs)

    def dump(self, path: Path) -> None:
        """Dump the model to file in yaml format."""
        dump_yaml(path, self)

    @classmethod
    def load(cls: type[BaseModelT], path: Path) -> BaseModelT:
        """Load the model from file in yaml format."""
        return cls.parse_obj(load_yaml(path))

    def checksum(self):
        """Calculate the checksum of the model."""
        return checksum_str(self.json(sort_keys=True))


class ReportConfig(BaseModel):
    """ReportConfig Model."""

    type: str
    name: str = ""


class WindowConfig(BaseModel):
    """WindowConfig Model."""

    initial_offset: float = 0.0
    bounds: tuple[float, float]
    t_step: float = 0.0
    n_trials: int = 1
    trial_steps_value: float = 0.0
    trial_steps_label: str = ""
    window_type: str = ""


class TrialStepsConfig(BaseModel):
    """TrialStepsConfig Model."""

    class Config(BaseModel.Config):
        """Custom Model Config."""

        extra = Extra.allow

    function: str
    initial_offset: float = 0.0
    bounds: tuple[float, float]


class NeuronClassConfig(BaseModel):
    """NeuronClassConfig Model."""

    query: Union[dict[str, Any], list[dict[str, Any]]] = Field(..., alias="$query")
    target: Optional[str] = Field(None, alias="$target")
    limit: Optional[int] = Field(None, alias="$limit")
    gids: Optional[list[int]] = Field(None, alias="$gids")

    @root_validator(pre=True)
    def assign_query(cls, values):
        """Move to $query all the query parameters, if needed."""
        if "$query" in values:
            return values
        new_values = {"$query": {}}
        for key, val in values.items():
            if key.startswith("$"):
                new_values[key] = val
            else:
                new_values["$query"][key] = val
        return new_values


class ExtractionConfig(BaseModel):
    """ExtractionConfig Model."""

    report: ReportConfig
    neuron_classes: dict[str, NeuronClassConfig] = {}
    limit: Optional[int] = None
    target: Optional[str] = None
    windows: dict[str, Union[str, WindowConfig]] = {}
    trial_steps: dict[str, TrialStepsConfig] = {}


class FeaturesConfig(BaseModel):
    """FeaturesConfig Model."""

    # do not consider id in the checksum
    id: Optional[int] = Field(None, exclude=True)
    type: str
    name: Optional[str] = None
    groupby: list[str]
    function: str
    neuron_classes: list[str] = []
    windows: list[str] = []
    params: dict[str, Any] = {}
    params_product: dict[str, Any] = {}
    params_zip: dict[str, Any] = {}
    suffix: str = ""


class SingleAnalysisConfig(BaseModel):
    """SingleAnalysisConfig Model."""

    output: Optional[Path] = None
    simulations_filter: dict[str, Any] = {}
    simulations_filter_in_memory: dict[str, Any] = {}
    extraction: ExtractionConfig
    features: list[FeaturesConfig] = []
    custom: dict[str, Any] = {}

    @validator("features")
    def assign_features_config_id(cls, lst):
        """Assign an incremental id to each FeaturesConfig."""
        for i, item in enumerate(lst):
            item.id = i
        return lst


class MultiAnalysisConfig(BaseModel):
    """MultiAnalysisConfig Model."""

    version: int
    simulation_campaign: Path
    output: Path
    clear_cache: bool = False
    simulations_filter: dict[str, Any] = {}
    simulations_filter_in_memory: dict[str, Any] = {}
    analysis: dict[str, SingleAnalysisConfig]
    custom: dict[str, Any] = {}

    @validator("version")
    def version_match(cls, version):
        """Verify that the config version is supported."""
        if version != CONFIG_VERSION:
            raise ValueError(f"Only config version {CONFIG_VERSION} is supported.")
        return version


if __name__ == "__main__":
    import yaml

    # print the json schema of the model in yaml format,
    # to be used only to update the current schema
    print(yaml.safe_dump(MultiAnalysisConfig.schema(), sort_keys=False))
