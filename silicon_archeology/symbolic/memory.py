"""
Symbolic Memory Model using Z3 Array theory with Little-Endian semantics.
"""

from typing import Optional, List
import z3


class SymbolicMemory:
    def __init__(self, name: str = "mem", initial_array: Optional[z3.ArrayRef] = None):
        self.address_sort = z3.BitVecSort(64)
        self.byte_sort = z3.BitVecSort(8)
        if initial_array is not None:
            self.memory = initial_array
        else:
            self.memory = z3.Array(name, self.address_sort, self.byte_sort)

    def clone(self, new_name: Optional[str] = None) -> "SymbolicMemory":
        return SymbolicMemory(
            name=new_name or "mem_copy",
            initial_array=self.memory
        )

    def read_byte(self, addr: z3.BitVecRef) -> z3.BitVecRef:
        if addr.size() < 64:
            addr = z3.ZeroExt(64 - addr.size(), addr)
        return z3.Select(self.memory, addr)

    def write_byte(self, addr: z3.BitVecRef, val: z3.BitVecRef) -> None:
        if addr.size() < 64:
            addr = z3.ZeroExt(64 - addr.size(), addr)
        if val.size() != 8:
            val = z3.Extract(7, 0, val)
        self.memory = z3.Store(self.memory, addr, val)

    def read(self, addr: z3.BitVecRef, bit_width: int) -> z3.BitVecRef:
        """Read a little-endian bit_width (8, 16, 32, 64) integer from memory."""
        if addr.size() < 64:
            addr = z3.ZeroExt(64 - addr.size(), addr)

        num_bytes = bit_width // 8
        if num_bytes <= 1:
            return self.read_byte(addr)

        bytes_list: List[z3.BitVecRef] = []
        for i in reversed(range(num_bytes)):
            offset_addr = addr + z3.BitVecVal(i, 64)
            bytes_list.append(self.read_byte(offset_addr))

        # Big-endian concatenation makes the MSB byte first in Concat,
        # which matches little-endian layout on disk
        res = bytes_list[0]
        for b in bytes_list[1:]:
            res = z3.Concat(res, b)
        return res

    def write(self, addr: z3.BitVecRef, val: z3.BitVecRef, bit_width: int) -> None:
        """Write a little-endian bit_width integer into memory."""
        if addr.size() < 64:
            addr = z3.ZeroExt(64 - addr.size(), addr)

        num_bytes = bit_width // 8
        for i in range(num_bytes):
            byte_val = z3.Extract(i * 8 + 7, i * 8, val)
            offset_addr = addr + z3.BitVecVal(i, 64)
            self.write_byte(offset_addr, byte_val)
