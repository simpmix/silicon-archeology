"""
Control Flow Graph (CFG) representation with dominator tree and loop analysis.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Tuple
from silicon_archeology.ir.instructions import Stmt, Branch, Jump, Return


@dataclass
class BasicBlock:
    label: str
    stmts: List[Stmt] = field(default_factory=list)
    predecessors: Set[str] = field(default_factory=set)
    successors: Set[str] = field(default_factory=set)

    @property
    def terminator(self) -> Optional[Stmt]:
        if not self.stmts:
            return None
        last = self.stmts[-1]
        if isinstance(last, (Branch, Jump, Return)):
            return last
        return None

    def add_stmt(self, stmt: Stmt) -> None:
        self.stmts.append(stmt)


@dataclass
class Loop:
    header: str
    latch: str
    body: Set[str]
    exits: Set[Tuple[str, str]] = field(default_factory=set)  # (inside_block, outside_block)


class ControlFlowGraph:
    def __init__(self, entry_label: str = "entry"):
        self.entry_label: str = entry_label
        self.blocks: Dict[str, BasicBlock] = {}
        self.idom: Dict[str, str] = {}
        self.dominators: Dict[str, Set[str]] = {}
        self.loops: List[Loop] = []

    def get_or_create_block(self, label: str) -> BasicBlock:
        if label not in self.blocks:
            self.blocks[label] = BasicBlock(label=label)
        return self.blocks[label]

    def add_edge(self, src: str, dst: str) -> None:
        src_bb = self.get_or_create_block(src)
        dst_bb = self.get_or_create_block(dst)
        src_bb.successors.add(dst)
        dst_bb.predecessors.add(src)

    def finalize_edges(self) -> None:
        """Populate successor and predecessor sets from block terminators."""
        for label, bb in list(self.blocks.items()):
            bb.successors.clear()
        for label, bb in list(self.blocks.items()):
            term = bb.terminator
            if isinstance(term, Branch):
                self.add_edge(label, term.target)
                self.add_edge(label, term.fallthrough)
            elif isinstance(term, Jump):
                self.add_edge(label, term.target)
            elif isinstance(term, Return):
                pass

    def compute_dominators(self) -> None:
        """Compute dominator sets and immediate dominators using iterative dataflow."""
        all_nodes = set(self.blocks.keys())
        if not all_nodes or self.entry_label not in self.blocks:
            return

        self.dominators = {node: set(all_nodes) for node in all_nodes}
        self.dominators[self.entry_label] = {self.entry_label}

        changed = True
        while changed:
            changed = False
            for node in all_nodes:
                if node == self.entry_label:
                    continue
                preds = self.blocks[node].predecessors
                if not preds:
                    new_dom = {node}
                else:
                    new_dom = set.intersection(*(self.dominators[p] for p in preds)) | {node}

                if new_dom != self.dominators[node]:
                    self.dominators[node] = new_dom
                    changed = True

        # Immediate dominators
        self.idom.clear()
        for node in all_nodes:
            if node == self.entry_label:
                continue
            strict_doms = self.dominators[node] - {node}
            for d in strict_doms:
                # d is idom if there is no other strict dominator that d strictly dominates
                if all(d not in (self.dominators[other] - {other}) for other in strict_doms if other != d):
                    self.idom[node] = d
                    break

    def detect_loops(self) -> List[Loop]:
        """Detect natural loops via back-edges where dst dominates src."""
        self.compute_dominators()
        self.loops.clear()

        for src, bb in self.blocks.items():
            for dst in bb.successors:
                # Back edge: dst dominates src
                if dst in self.dominators.get(src, set()):
                    # dst is the loop header, src is the latch
                    body = self._extract_natural_loop_body(dst, src)
                    # Find exits
                    exits = set()
                    for b in body:
                        for succ in self.blocks[b].successors:
                            if succ not in body:
                                exits.add((b, succ))
                    self.loops.append(Loop(header=dst, latch=src, body=body, exits=exits))

        return self.loops

    def _extract_natural_loop_body(self, header: str, latch: str) -> Set[str]:
        body = {header, latch}
        stack = [latch] if latch != header else []
        while stack:
            curr = stack.pop()
            for pred in self.blocks[curr].predecessors:
                if pred not in body:
                    body.add(pred)
                    stack.append(pred)
        return body

    def reverse_post_order(self) -> List[str]:
        """Compute reverse post-order traversal starting from entry."""
        visited = set()
        order = []

        def dfs(node: str):
            visited.add(node)
            for succ in sorted(self.blocks[node].successors):
                if succ not in visited and succ in self.blocks:
                    dfs(succ)
            order.append(node)

        if self.entry_label in self.blocks:
            dfs(self.entry_label)

        # Include unreachable blocks if any
        for b in sorted(self.blocks.keys()):
            if b not in visited:
                dfs(b)

        order.reverse()
        return order
