from dataclasses import dataclass
from pycardano import PlutusData

@dataclass()
class Game(PlutusData):
    CONSTR_ID = 1
    target: int
    state: int
    price: int
    pool: int

@dataclass()
class Player(PlutusData):
    CONSTR_ID = 2
    paymentCred: bytes
    stakingCred: bytes
    ticket_number: int

@dataclass()
class tunaDatum(PlutusData):
    CONSTR_ID = 0
    block: int
    block_hash: bytes
    leading_zeros: int
    target_number: int
    epoch_time: int
    posix_time: int
    merkle_root: bytes

@dataclass()
class prizePool(PlutusData):
    CONSTR_ID = 3
    prizepool: bytes # b'fish'

@dataclass()
class STATE(PlutusData):
    # StateRedeemer
    CONSTR_ID = 0
    state: int
