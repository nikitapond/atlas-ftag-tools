from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
from numpy.lib import recfunctions as rfn

__all__ = ["Transform"]

Batch = dict[str, np.ndarray]


@dataclass
class Transform:
    variable_map: dict[str, dict[str, str]] | None = None
    ints_map: dict[str, dict[str, dict[int, int]]] | None = None
    floats_map: dict[str, dict[str, str | Callable]] | None = None
    insert_vars: dict[str, dict[str, float | int | bool]] | None = None
    def __post_init__(self):
        self.variable_map = self.variable_map or {}
        self.variable_map_inv = {
            k: {v: k for k, v in v.items()} for k, v in self.variable_map.items()
        }
        self.ints_map = self.ints_map or {}
        self.floats_map = self.floats_map or {}
        self.insert_vars = self.insert_vars or {}
        # convert string to numpy function
        for group, map_dict in self.floats_map.items():
            for variable, func in map_dict.items():
                self.floats_map[group][variable] = getattr(np, func)

    def __call__(self, batch: Batch) -> Batch:
        batch = self.map_ints(batch)
        batch = self.map_floats(batch)
        batch = self.insert_variables(batch)
        return self.map_variables(batch)

    def insert_variables(self, batch: Batch) -> Batch:
        """
        Inserts new variable with a provided default value if it isn't found in the batch.
        
        Parameters:
        -----------
        batch : Batch
            Dict of structured numpy arrays.

        Returns
        -------
        Batch
            Dict of structured numpy arrays with new inserted variables.
        """

        assert self.insert_vars is not None
        for group, insert in self.insert_vars.items():
            if group not in batch:
                continue
            for variable, value in insert.items():
                if variable in batch[group].dtype.names:
                    continue
                # create a new array with a single constant value
                if isinstance(value, bool):
                    new_dt = 'b1'
                elif isinstance(value, float):
                    new_dt = 'f4'
                elif isinstance(value, int):
                    new_dt = 'i4'
                else:
                    raise TypeError(f"Unknown type {type(value)} for {variable}")
                new_values = np.full(batch[group].shape, value, dtype=new_dt)
                # append the new field
                batch[group] = rfn.append_fields(batch[group], variable, new_values, usemask=False)
        return batch
        # print("lol", flush=True)
        # assert self.insert_vars is not None
        # for group, insert in self.insert_vars.items():
        #     print("lol2,", group)
        #     if group not in batch:
        #         continue
        #     for variable, value in insert.items():
        #         if variable in batch[group].dtype.names:
        #             continue
        #         print("here")
        #         new_dt = np.dtype(batch[group].dtype.descr + 
        #                           [(variable, 'f4' if isinstance(value, float) else 'i4')])
        #         arr_out = np.empty(batch[group].shape, dtype=new_dt)
        #         arr_out[:] = batch[group]
        #         arr_out[variable] = value
        #         batch[group] = arr_out
        # return batch            

    def map_variables(self, batch: Batch) -> Batch:
        """
        Rename variables in a batch of data.

        Parameters
        ----------
        batch : Batch
            Dict of structured numpy arrays.

        Returns
        -------
        Batch
            Dict of structured numpy arrays with renamed variables.
        """
        assert self.variable_map is not None
        for group in self.variable_map:
            if group in batch:
                batch[group] = batch[group].astype(self.map_dtype(group, batch[group].dtype))
        return batch

    def map_ints(self, batch: Batch) -> Batch:
        """
        Map integer values to new values.

        Parameters
        ----------
        batch : Batch
            Dict of structured numpy arrays.

        Returns
        -------
        Batch
            Dict of structured numpy arrays with mapped integer values.
        """
        assert self.ints_map is not None
        for group, map_dict in self.ints_map.items():
            if group not in batch:
                continue
            for variable, int_map in map_dict.items():
                if variable not in batch[group].dtype.names:
                    continue
                data = batch[group][variable]
                for old, new in int_map.items():
                    data[data == old] = new
        return batch

    def map_floats(self, batch: Batch) -> Batch:
        """
        Transform float values.

        Parameters
        ----------
        batch : Batch
            Dict of structured numpy arrays.

        Returns
        -------
        Batch
            Dict of structured numpy arrays with transformed float values.
        """
        assert self.floats_map is not None
        for group, map_dict in self.floats_map.items():
            if group not in batch:
                continue
            for variable, func in map_dict.items():
                assert callable(func)
                batch[group][variable] = func(batch[group][variable])
        return batch

    def map_dtype(self, name: str, dtype: np.dtype) -> np.dtype:
        assert self.variable_map is not None
        if not (map_dict := self.variable_map.get(name.lstrip("/"))):
            return dtype
        names = list(dtype.names)
        for old, new in map_dict.items():
            if old in names and new in names:
                raise ValueError(f"Variables {old, new} already exists in {name}.")
        return np.dtype([(map_dict.get(name, name), dtype[name]) for name in names])

    def map_variable_names(self, name: str, variables: list[str], inverse=False) -> list[str]:
        variable_map = self.variable_map_inv if inverse else self.variable_map
        if not (map_dict := variable_map.get(name.lstrip("/"))):
            return variables
        return [map_dict.get(name, name) for name in variables]
