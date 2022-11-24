import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from numpy.testing import assert_equal
from pandas.api.types import is_integer_dtype

from blueetl import utils as test_module
from blueetl.constants import DTYPES


@pytest.mark.parametrize(
    "x, expected",
    [
        ([], []),
        ((), ()),
        (None, [None]),
        ("", [""]),
        ("a", ["a"]),
        (["a"], ["a"]),
        (("a",), ("a",)),
    ],
)
def test_ensure_list(x, expected):
    result = test_module.ensure_list(x)
    assert result == expected


@pytest.mark.parametrize("dtypes", [None, DTYPES])
def test_ensure_dtypes(dtypes):
    df = pd.DataFrame([{k: i for i, k in enumerate(DTYPES)}])
    df["other"] = 99
    df.index = pd.MultiIndex.from_frame(df)

    result = test_module.ensure_dtypes(df, desired_dtypes=dtypes)

    expected = [*list(DTYPES.values()), np.int64]
    assert_equal(result.dtypes.to_numpy(), expected)
    # convert any int to int64 in the expected list
    expected = [np.int64 if is_integer_dtype(item) else item for item in expected]
    assert_equal(result.index.dtypes.to_numpy(), expected)


def test_import_by_string():
    name = "json.load"
    result = test_module.import_by_string(name)
    assert result is json.load


def test_resolve_path(tmp_path):
    subdir = Path("subdir")
    my_file = Path("my_file")
    my_symlink = Path("my_symlink")
    non_existent = Path("non_existent")

    tmp_path = tmp_path.resolve()
    subdir_absolute = tmp_path / subdir
    my_file_absolute = tmp_path / subdir / my_file
    my_symlink_absolute = tmp_path / subdir / my_symlink
    non_existent_absolute = tmp_path / subdir / non_existent

    subdir_absolute.mkdir()
    my_file_absolute.touch()
    my_symlink_absolute.symlink_to(my_file)

    result = test_module.resolve_path(tmp_path, subdir, my_file, symlinks=False)
    assert result == my_file_absolute

    result = test_module.resolve_path(tmp_path, subdir, my_file, symlinks=True)
    assert result == my_file_absolute

    result = test_module.resolve_path(tmp_path, subdir, my_symlink, symlinks=False)
    assert result == my_symlink_absolute

    result = test_module.resolve_path(tmp_path, subdir, my_symlink, symlinks=True)
    assert result == my_file_absolute

    result = test_module.resolve_path(tmp_path, subdir, non_existent, symlinks=False)
    assert result == non_existent_absolute

    result = test_module.resolve_path(tmp_path, subdir, non_existent, symlinks=True)
    assert result == non_existent_absolute


def test_dump_load_yaml_roundtrip(tmp_path):
    data = {
        "dict": {"str": "mystr", "int": 123},
        "list_of_int": [1, 2, 3],
        "list_of_str": ["1", "2", "3"],
        "path": Path("/custom/path"),
    }
    expected_content = """
dict:
  str: mystr
  int: 123
list_of_int:
- 1
- 2
- 3
list_of_str:
- '1'
- '2'
- '3'
path: !path '/custom/path'
    """
    filepath = tmp_path / "test.yaml"

    test_module.dump_yaml(filepath, data)
    dumped_content = filepath.read_text(encoding="utf-8")
    assert dumped_content.strip() == expected_content.strip()

    loaded_data = test_module.load_yaml(filepath)
    assert loaded_data == data
