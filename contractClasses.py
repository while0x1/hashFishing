from opshin.prelude import *
from pycardano import PlutusData

@dataclass()
class Game(PlutusData):
    CONSTR_ID = 1
    target: int
    state: int
    price: int
    pool: int

@dataclass()
class swapAsset(PlutusData):
    CONSTR_ID = 5
    owner: bytes
    stake: bytes
    cost: int    

@dataclass()
class Player(PlutusData):
    CONSTR_ID = 2
    cred: List[List[bytes]]

@dataclass()
class tunaDatum(PlutusData):
    CONSTR_ID = 0
    block: int
    block_hash: bytes
    lz: int
    target_number: int
    et: int
    pt: int
    m: bytes

@dataclass()
class STATE(PlutusData):
    # StateRedeemer
    CONSTR_ID = 0
    state: int
    index: int
    
@dataclass()
class prizePool(PlutusData):
    CONSTR_ID = 3
    prizepool: bytes # b'fish'

