from blockfrost import ApiUrls
from pycardano import *
import sys
from contractClasses import Player,Game,STATE, prizePool
from staticVars import *
import time
#PREVIEW TUNA V2 ADDRESS =================
'addr_test1wpwadl46nw6m80lqls3a4pgelmtm4z7980vr3d77clzzy6sfgnzsr'

policyId = 'd4125e15eaac9126dddb1f9e1e62fbaaf78a33c333e470849eba9720'

manualUtxoSelection = False

hdwallet = HDWallet.from_mnemonic(SEED)
hdwallet_stake = hdwallet.derive_from_path("m/1852'/1815'/0'/2/0")
stake_public_key = hdwallet_stake.public_key
stake_vk = PaymentVerificationKey.from_primitive(stake_public_key)
hdwallet_spend = hdwallet.derive_from_path("m/1852'/1815'/0'/0/0")
spend_public_key = hdwallet_spend.public_key
payment_vkey = PaymentVerificationKey.from_primitive(spend_public_key)
payment_skey = ExtendedSigningKey.from_hdwallet(hdwallet_spend)
stake_vkey = PaymentVerificationKey.from_primitive(stake_public_key)


if NET == 'TESTNET':
        #chain_context = BlockFrostChainContext(project_id=BLOCK_FROST_PROJECT_ID,base_url=ApiUrls.preview.value,)
        if USE_BF:
            chain_context = BlockFrostChainContext(project_id=BLOCK_FROST_PROJECT_ID,base_url=ApiUrls.preview.value,)
        else:
            chain_context = OgmiosV6ChainContext(OGMIOS_IP_TNET,network=Network.TESTNET) 
        address = Address(payment_vkey.hash(),stake_vkey.hash(),network=Network.TESTNET)
        script_address= 'addr_test1wrg54azh8sn5f4vqpaktvdj33t4kqtscuftg0ul3epmrj4gywtsae'
        refscript_utxos = chain_context.utxos('addr_test1vqgx04a3wjj3zfvdn08lrnxg2ma3m9guh3wyqkafjj85j9qjyrplj')
else:
        if USE_BF:
            chain_context = BlockFrostChainContext(project_id=BLOCK_FROST_PROJECT_ID,base_url=ApiUrls.mainnet.value,)
        else:    
            chain_context = OgmiosV6ChainContext(OGMIOS_IP_MNET,network=Network.MAINNET)
        address = Address(payment_vkey.hash(),stake_vkey.hash(),network=Network.MAINNET)
        script_address = 'addr1wyd77xezy82ua46vgknuh9xdvhyy9u7ulkxqdh2w3lz6aqcsw0usm'
        refscript_utxos = chain_context.utxos('addr1vygx04a3wjj3zfvdn08lrnxg2ma3m9guh3wyqkafjj85j9qfvhash')


print(f'Imported Wallet: {address}')
time.sleep(2)

for utxo in refscript_utxos:
    if utxo.output.script:
        print('Reference Script UTxO Acquired')
        ref_script_utxo = utxo

contractAddress = script_address
contractUtxos = chain_context.utxos(contractAddress)

gameToken = MultiAsset.from_primitive({bytes.fromhex(policyId): {b'GAME': 1}})
playerToken = MultiAsset.from_primitive({bytes.fromhex(policyId): {b'PLAYER': 1}}) 

gameFound = False
playerFound = False
poolUtxo = 0
playerTix = ''
for u in contractUtxos:
    if u.output.amount.multi_asset == playerToken:
        rawPlutus = RawPlutusData.from_cbor(u.output.datum.cbor)  
        if rawPlutus.data.value[0] == b'':
            playerUtxo = u
            #emptyTicket
            playerCred = rawPlutus.data.value[0]
            playerTix = rawPlutus.data.value[2]
            playerFound = True
    elif u.output.amount.multi_asset == gameToken:
        gameUtxo = u
        rawPlutus = RawPlutusData.from_cbor(u.output.datum.cbor)  
        gameBlock = rawPlutus.data.value[0]
        gameState = rawPlutus.data.value[1]
        gamePrice = rawPlutus.data.value[2]
        gamePool = rawPlutus.data.value[3]
        gameFound = True
        print('GameTokenFound')
    if playerFound and gameFound:
        print('AvailableTicketFound')
        break

if gameFound and gamePool != 0:
    for u in contractUtxos:
        if u.output.datum.cbor == b'\xd8|\x9fDfish\xff':  #b'\xd8y\x9fDfish\xff'
            print('FoundPoolUtxo')
            poolUtxo = u

if playerFound: 
    print(f'Available Tickets found - creating Datum for ticket no. {playerTix}')
    playerDatum = Player(payment_vkey.hash().payload,stake_vkey.hash().payload,playerTix)
    gameDatumOut = Game(gameBlock,gameState,gamePrice,gamePool + gamePrice)
    print(f'Game draw @ block {gameBlock} game price {gamePrice}')
else:
    print('Didndt Find Tickets')
    sys.exit()       

prizePoolDatum = prizePool(b'fish')
#STATE 0 for BUY Tickets
entry_redeemer = Redeemer(STATE(0))
game_redeemer = Redeemer(STATE(0))
pool_redeemer = Redeemer(STATE(0))

if manualUtxoSelection:
    claimerUtxos = chain_context.utxos(address)
    #findCollateral
    collateralUtxo = ''
    for n in claimerUtxos:
        if not n.output.amount.multi_asset and n.output.amount.coin >= 6000000:
            print('CollateralFound')
            collateralUtxo = n
            break
    if collateralUtxo == '':
        print('Couldnt Find Collateral -- exiting')
        sys.exit()
    entryUtxo = ''
    for n in claimerUtxos:
        if n.output.amount.coin >= gamePrice and n != collateralUtxo and not n.output.amount.multi_asset:
            print('Found Ticket Payment Utxo')
            entryUtxo = n
            break
    if entryUtxo == '':
        print('Couldnt Find Entry fee utxo --> exiting..')
        sys.exit()
    feeUtxo = ''
    feeUtxoRequired = False
    if entryUtxo.output.amount.coin + collateralUtxo.output.amount.coin < gamePrice + 2000000 + 5000000:
        print('SearchingForFeeUtxo')
        feeUtxoRequired = True
        for n in claimerUtxos:
            if n.output.amount.coin >= 2000000 and n != collateralUtxo and n != entryUtxo and not n.output.amount.multi_asset:
                feeUtxo = n
                print('Fee utxo acquired')
    if feeUtxo == '' and feeUtxoRequired:
        print('Couldnt Find Fee Utxo --> exiting..')
        sys.exit()

claimerUtxos = chain_context.utxos(address)
#BuildTransaction
builder = TransactionBuilder(chain_context)
collateralUtxo = ''
for n in claimerUtxos:
    if not n.output.amount.multi_asset and n.output.amount.coin >= 6000000:
        print('CollateralFound')
        collateralUtxo = n
        break

if collateralUtxo == '':
    pass
    #print('Need Collateral UTXO >= 6 ADA')
    #sys.exit()
else:
    builder.collaterals.append(collateralUtxo)


if manualUtxoSelection:
    builder.collaterals.append(collateralUtxo)
    builder.add_input(entryUtxo)
    if feeUtxoRequired:
        builder.add_input(feeUtxo)
else:
    builder.add_input_address(address)

addPool = False    
builder.add_script_input(playerUtxo, script=ref_script_utxo, redeemer=entry_redeemer)
builder.add_script_input(gameUtxo, script=ref_script_utxo, redeemer=game_redeemer)
if gamePool == 0:
    print('First Ticket - no Pool UTxo Required')
    builder.add_output(TransactionOutput(script_address,Value(gameDatumOut.price), datum=prizePoolDatum))
else:
    if poolUtxo != 0:
        addPool = True
        builder.add_script_input(poolUtxo,script=ref_script_utxo, redeemer=pool_redeemer)
        builder.add_output(TransactionOutput(script_address,Value(gamePool + gameDatumOut.price), datum=prizePoolDatum))
    else:
        print('PoolUTxO Error')
        sys.exit()
#min_val = min_lovelace_post_alonzo(TransactionOutput(address, Value(0, playerToken),chain_context))
if addPool:
    print('Adding PoolUtxo Input')
    
builder.add_output(TransactionOutput(script_address,Value(1500000,playerToken), datum=playerDatum))
builder.add_output(TransactionOutput(script_address,Value(1500000,gameToken), datum=gameDatumOut))


#builder._estimate_fee = lambda : 380000
signed_tx = builder.build_and_sign([payment_skey], address)

#builder.add_output(TransactionOutput(address,Value(6000000)))
#builder.add_output(TransactionOutput(address,Value(6000000)))
#builder.add_output(TransactionOutput(address,Value(6000000)))


#print(signed_tx.transaction_body.hash().hex())

rt = input('Review Transaction? (Y/N)')

if rt == 'Y':
    print(signed_tx)
    print()
    
print('Submit Transaction? (Y/N)')
x = input()

if x == 'Y':
    chain_context.submit_tx(signed_tx.to_cbor())
    print(f'Transaction submitted: {signed_tx.id}')
else:
    print('Sequence Aborted...') 
'''
chain_context.submit_tx(signed_tx.to_cbor())
print(f'Transaction submitted: {signed_tx.id}')
'''

txFound = False
while True:  
    print('Searching for Tx Confirmation...')
    time.sleep(2)
    print('.')
    time.sleep(2)
    print('..')
    time.sleep(2)
    print('...')
    time.sleep(2)
    ut = chain_context.utxos(script_address)
    for n in ut:
        if n.input.transaction_id == signed_tx.id:
            txFound = True
            print('Tx Complete')
            break
    if txFound:
        break
