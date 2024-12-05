from blockfrost import ApiUrls
from pycardano import *
from contractClasses import Game,Player, tunaDatum, STATE, prizePool
import sys
from staticVars import *
import time
import logging
import os
from logging.handlers import RotatingFileHandler


cwd = os.getcwd()
#print(cwd)
logdir = "/logs"
#CreateLogFiles

if not os.path.exists(cwd+logdir):
    os.makedirs(cwd+logdir)   
pathtologfile = cwd+logdir+ '/gameWatcher_log'
logger = logging.getLogger('gameWatcher_log')
handler = RotatingFileHandler(pathtologfile, maxBytes=400000, backupCount=4)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s',datefmt= '%d-%b-%y %H:%M:%S')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

logger.info("Game Watcher is looking for tunas...")

#counted from previous gameBlock not current block
RESET_BLOCKS = 10
ENTRY_PRICE = 3000000
GAME_RESET = False

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
    makerAddress = Address.from_primitive('addr_test1vq69dh482jjpwew7m6vz44q2y8w855gt58n0f9dc76zfhwcxtepu2')
    net = Network.TESTNET
    if USE_BF:
        chain_context = BlockFrostChainContext(project_id=BLOCK_FROST_PROJECT_ID,base_url=ApiUrls.preview.value,)
    else:
        chain_context = OgmiosV6ChainContext(OGMIOS_IP_TNET,network=net)
else:
    makerAddress = Address.from_primitive('addr1vy69dh482jjpwew7m6vz44q2y8w855gt58n0f9dc76zfhwcardan0')
    net = Network.MAINNET
    if USE_BF:
        chain_context = BlockFrostChainContext(project_id=BLOCK_FROST_PROJECT_ID,base_url=ApiUrls.mainnet.value,)
    else:
        chain_context = OgmiosV6ChainContext(OGMIOS_IP_MNET,network=net)

 
    
address = Address(payment_vkey.hash(),stake_vkey.hash(),network=net)
script_address= Address(ScriptHash(bytes.fromhex(SCRIPT_HASH)),network=net)        
refscript_utxos = chain_context.utxos(Address(VerificationKeyHash(bytes.fromhex(REFSCRIPT_HASH)),network=net))
for utxo in refscript_utxos:
    if utxo.output.script:
            #print(utxo)
        ref_script_utxo = utxo
        logger.info('Reference script UTXO found')

loopCount = 0
       
while True:
    try:
        claimerUtxos = chain_context.utxos(address)
        colUtxo = False
        totalAda = 0
        totalUtxo = 0
        for n in claimerUtxos:
            totalAda += n.output.amount.coin
            totalUtxo += 1 
            if n.output.amount.multi_asset and n.output.amount.coin >= 6000000:
                colUtxo =True
        if not colUtxo:
            logger.info('No Collateral Found - creating Transaction for Collateral utxo')
            #create A transaction to ensure you have 6ADA Collateral
            builder = TransactionBuilder(chain_context)
            builder.add_input_address(address)
            builder.add_output(TransactionOutput(address,Value(6000000)))
            signed_tx = builder.build_and_sign([payment_skey], address)
            #print(signed_tx.transaction_body.hash().hex())
            chain_context.submit_tx(signed_tx.to_cbor())
            colFound = False
            while True:  
                logger.info('Searching for Collateral Tx Confirmation...')
                time.sleep(8)
                ut = chain_context.utxos(script_address)
                for n in ut:
                    if n.input.transaction_id == signed_tx.id:
                        colFound = True
                        logger.info('Collateral Tx Complete')
                        break
                if colFound:
                    break
        
        tunaUtxos = chain_context.utxos(TUNA_CONTRACT)

        blockNumber = 0 
        for u in tunaUtxos:
            if u.output.amount.multi_asset: 
                if list(u.output.amount.multi_asset.keys())[0].payload == TUNA_POLICY:
                    rawPlutus = RawPlutusData.from_cbor(u.output.datum.cbor)
                    tunaUtxo = u
                    #tunaBlock = rawPlutus.data.value[0]
                    blockNumber = rawPlutus.data.value[0]
                    blockHash = rawPlutus.data.value[1]
                    winningInt = blockHash[31] % 16
                    #print(f'Winning Ticket found -- {winningInt}')

        fishingUtxos = chain_context.utxos(script_address)

        gameUtxo = ''
        playerUtxo = ''

        gameToken = MultiAsset.from_primitive({bytes.fromhex(POLICY): {b'GAME': 1}})
        playerToken = MultiAsset.from_primitive({bytes.fromhex(POLICY): {b'PLAYER': 1}}) 

        winnerFound = False
        prizeUtxos= []
        playerCred = b''
        playerStake = b''

        for u in fishingUtxos:
            if u.output.amount.multi_asset == gameToken:
                gameUtxo = u
                rawPlutus = RawPlutusData.from_cbor(u.output.datum.cbor)  
                gameBlock = rawPlutus.data.value[0]
                gameState = rawPlutus.data.value[1]
                gamePrice = rawPlutus.data.value[2]
                gameEntries = rawPlutus.data.value[3]
        
            elif u.output.amount.multi_asset == playerToken:
                playerUtxo = u
                playerRawPlutus = RawPlutusData.from_cbor(u.output.datum.cbor) 
                playerCred = playerRawPlutus.data.value[0][winningInt][0]
                playerStake = playerRawPlutus.data.value[0][winningInt][1]
                playerDatum = Player(playerRawPlutus.data.value[0])
                if playerCred != b'':
                    winnerFound =  True
            elif not u.output.amount.multi_asset:
                prizeUtxos.append(u)   
        #CheckForPrizeWinners
        if blockNumber ==  gameBlock:
            #ClaimPrize If Winner Found and GameState 0
            if winnerFound and gameState == 0:
                gameDatumOut = Game(gameBlock,gameState + 2,gamePrice,gameEntries)
                logger.info('Winner Found Building Prize Transaction!')
                logger.info(playerDatum)
                claim_redeemer1 = Redeemer(STATE(2,0))
                claim_redeemer2= Redeemer(STATE(2,0))
                prizePoolDatum = prizePool(b'fish')
                prizeFound = False
                for u in prizeUtxos:
                    if u.output.datum.cbor ==  b'\xd8|\x9fDfish\xff':  #b'\xd8y\x9fDfish\xff'
                            logger.info('FoundPoolUtxo')
                            prizeUtxo = u
                            prizeFound = True
                if not prizeFound:
                    logger.info('No Prize Utxos')
                else:
                    logger.info('Prize Utxo Identified - Building Transaction')       
                    builder = TransactionBuilder(chain_context)
                    collateralUtxo = ''
                    for n in claimerUtxos:
                        if not n.output.amount.multi_asset and n.output.amount.coin >= 6000000:
                            logger.info('CollateralFound')
                            collateralUtxo = n
                            builder.collaterals.append(n)
                            break

                    builder.add_script_input(playerUtxo, script=ref_script_utxo, redeemer=claim_redeemer1)
                    builder.add_script_input(gameUtxo, script=ref_script_utxo, redeemer=claim_redeemer2)
                    builder.add_input_address(address)
                    builder.reference_inputs.add(tunaUtxo)


                    builder.add_script_input(prizeUtxo, script=ref_script_utxo, redeemer=Redeemer(STATE(2,0)))
                        
                    builder.add_output(TransactionOutput(script_address,Value(10000000,playerToken), datum=playerDatum))
                    builder.add_output(TransactionOutput(script_address,Value(1500000,gameToken), datum=gameDatumOut))
                    if playerStake != b'':
                        payment_hash = VerificationKeyHash.from_primitive(playerCred)
                        staking_hash = VerificationKeyHash.from_primitive(playerStake)
                        
                        if NET == 'TESTNET':
                            winnersAddress = Address(payment_hash,staking_hash,network=Network.TESTNET)
                        else:        
                            winnersAddress = Address(payment_hash,staking_hash,network=Network.MAINNET)
                    else:
                        payment_hash = VerificationKeyHash.from_primitive(playerCred)
                        if NET == 'TESTNET':
                            
                            winnersAddress = Address(payment_hash,network=Network.TESTNET)
                        else:
                            winnersAddress = Address(payment_hash,network=Network.MAINNET)
                    
                    bonus = False
                    if gameEntries > gamePrice * 3:
                        prize = gameEntries - gamePrice
                        logger.info('makers bonus found')
                        bonus = True
                    else:
                        prize = gameEntries 
                    
                    builder.add_output(TransactionOutput(winnersAddress,Value(prize)))

                    if bonus:
                        if gamePrice >= 3000000:
                            builder.add_output(TransactionOutput(makerAddress,Value(gamePrice - 2000000)))
                            builder.add_output(TransactionOutput(address,Value(2000000)))
                        else:
                            builder.add_output(TransactionOutput(makerAddress,Value(gamePrice)))

                    #print(builder.outputs)
                    signed_tx = builder.build_and_sign([payment_skey], address)
                    #print(signed_tx.transaction_body.hash().hex())
                    chain_context.submit_tx(signed_tx.to_cbor())
                    logger.info(f'Success Winners Claimed Pool! --> {signed_tx.id}')

                    txFound = False
                    while True:  
                        logger.info('Searching for Tx Confirmation...')
                        time.sleep(8)
                        ut = chain_context.utxos(script_address)
                        for n in ut:
                            if n.input.transaction_id == signed_tx.id:
                                txFound = True
                                logger.info('Tx Complete')
                                break
                        if txFound:
                            break 
                        time.sleep(30)      
            #else:
            #    print('GameState not 0 or No winners Found')
        
        #noWinner - prizepoolreturn -----=========------------
        elif blockNumber > gameBlock and gameState == 0:
            
            if gameUtxo != '' :
                #Add GameState Condition statement here for pool return (in new contract)
                gameDatumOut = Game(gameBlock,gameState + 1,gamePrice,gameEntries)
                #noWinnerState5
                claim_redeemer1 = Redeemer(STATE(5,0))
                #needLogic which can identify the right playerToken winner here from the two datums..the hash and playerToken        
                builder = TransactionBuilder(chain_context)
                builder.add_script_input(gameUtxo, script=ref_script_utxo, redeemer=claim_redeemer1)
                builder.add_input_address(address)
                builder.reference_inputs.add(tunaUtxo)

                claimerUtxos = chain_context.utxos(address)
                #tryfindCollateral

                for n in claimerUtxos:
                    if not n.output.amount.multi_asset and n.output.amount.coin >= 6000000:
                        logger.info('CollateralFound')
                        builder.collaterals.append(n)
                        break

                builder.add_output(TransactionOutput(script_address,Value(1500000,gameToken), datum=gameDatumOut))
                signed_tx = builder.build_and_sign([payment_skey], address)
                chain_context.submit_tx(signed_tx.to_cbor())
                logger.info('NoWinner Transaction Submitted!')
                logger.info(signed_tx.id)
                time.sleep(30)
        #ResetPlayersAndGame
        elif blockNumber - gameBlock >= 2 and gameState > 0 and GAME_RESET:
            logger.info('Reset Game Available')
            if gameState == 1:
                gameDatumOut = Game(gameBlock + RESET_BLOCKS ,0,ENTRY_PRICE,gameEntries)
            elif gameState == 2:
                gameDatumOut = Game(gameBlock + RESET_BLOCKS ,0,ENTRY_PRICE,0)
            
            claim_redeemer1 = Redeemer(STATE(4,0))
            claim_redeemer2 = Redeemer(STATE(4,0))    

            playerDatum = Player([[b"",b""],[b"",b""],[b"",b""],[b"",b""],[b"",b""],[b"",b""],[b"",b""],[b"",b""],[b"",b""],[b"",b""],[b"",b""],[b"",b""],[b"",b""],[b"",b""],[b"",b""],[b"",b""]])

            builder = TransactionBuilder(chain_context)
            builder.add_input_address(address)

            claimerUtxos = chain_context.utxos(address)
            #tryfindCollateral
            cf = False
            for n in claimerUtxos:
                if not n.output.amount.multi_asset and n.output.amount.coin >= 6000000:
                    logger.info('CollateralFound')
                    builder.collaterals.append(n)
                    cf = True
                    break

            builder.reference_inputs.add(tunaUtxo)
            builder.add_script_input(gameUtxo, script=ref_script_utxo, redeemer=claim_redeemer1)
            builder.add_script_input(playerUtxo, script=ref_script_utxo, redeemer=claim_redeemer2)

            builder.add_output(TransactionOutput(script_address,Value(1500000,gameToken), datum=gameDatumOut))
            builder.add_output(TransactionOutput(script_address,Value(10000000,playerToken), datum=playerDatum))

            signed_tx = builder.build_and_sign([payment_skey], address)
            chain_context.submit_tx(signed_tx.to_cbor())
            logger.info(f'Game Reset ! New draw @ block {gameBlock + 8}')
            logger.info(signed_tx.id)
            time.sleep(30)   
        
        tRes = 0
        for n in playerDatum.cred:
            if n[0] != b'':
                tRes += 1  
        if loopCount == 240:
            loopCount = 0
            logger.info(f'Tuna block: {blockNumber}  Draw Block: {gameBlock} Game State: {gameState} Tickets Reserved: {tRes}')
        elif loopCount == 0:
            logger.info(f'Tuna block: {blockNumber}  Draw Block: {gameBlock} Game State: {gameState} Tickets Reserved: {tRes}')
            logger.info('Watcher Wallet:')
            logger.info(f'No. of Utxos: {totalUtxo}')
            logger.info(f'totalAda Available: {round(totalAda/1000000,1)}')
        
        loopCount += 1
        time.sleep(30)
    except Exception as e:
        logger.error(e)
        time.sleep(30)
