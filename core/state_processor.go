// Copyright 2015 The go-ethereum Authors
// This file is part of the go-ethereum library.
//
// The go-ethereum library is free software: you can redistribute it and/or modify
// it under the terms of the GNU Lesser General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// The go-ethereum library is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
// GNU Lesser General Public License for more details.
//
// You should have received a copy of the GNU Lesser General Public License
// along with the go-ethereum library. If not, see <http://www.gnu.org/licenses/>.

package core

import (
	"fmt"
	"math/big"
	"sort"
	"strconv"
	"time"

	"github.com/ethereum/go-ethereum/common"
	"github.com/ethereum/go-ethereum/consensus"
	"github.com/ethereum/go-ethereum/consensus/misc"
	"github.com/ethereum/go-ethereum/core/state"
	"github.com/ethereum/go-ethereum/core/types"
	"github.com/ethereum/go-ethereum/core/vm"
	"github.com/ethereum/go-ethereum/crypto"
	"github.com/ethereum/go-ethereum/params"
)

// StateProcessor is a basic Processor, which takes care of transitioning
// state from one point to another.
//
// StateProcessor implements Processor.
type StateProcessor struct {
	config *params.ChainConfig // Chain configuration options
	bc     *BlockChain         // Canonical block chain
	engine consensus.Engine    // Consensus engine used for block rewards
}

// NewStateProcessor initialises a new StateProcessor.
func NewStateProcessor(config *params.ChainConfig, bc *BlockChain, engine consensus.Engine) *StateProcessor {
	return &StateProcessor{
		config: config,
		bc:     bc,
		engine: engine,
	}
}

// Process processes the state changes according to the Ethereum rules by running
// the transaction messages using the statedb and applying any rewards to both
// the processor (coinbase) and any included uncles.
//
// Process returns the receipts and logs accumulated during the process and
// returns the amount of gas that was used in the process. If any of the
// transactions failed to execute due to insufficient gas it will return an error.
func (p *StateProcessor) Process(block *types.Block, statedb *state.StateDB, cfg vm.Config) (types.Receipts, []*types.Log, uint64, error) {
	defer func(start time.Time) {
		fmt.Printf("Execution state_process, block_number = %v ,cost time = %v\n", strconv.FormatUint(block.NumberU64(), 10), time.Since(start))
	}(time.Now())
	var (
		receipts    types.Receipts
		usedGas     = new(uint64)
		header      = block.Header()
		blockHash   = block.Hash()
		blockNumber = block.Number()
		allLogs     []*types.Log
		gp          = new(GasPool).AddGas(block.GasLimit())
	)
	vm.BlockDumpLogger(block, 100000, 1000)

	parityLogContext := vm.ParityLogContext{
		BlockHash:   block.Hash(),
		BlockNumber: block.NumberU64(),
	}
	tracer, err := vm.NewParityLogger(&parityLogContext, block.NumberU64(), 100000, 1000)
	if err != nil {
		return nil, nil, 0, fmt.Errorf("create parity logger failed: %w", err)
	}
	vm.GlobalParityLogger = tracer
	cfg.Debug = true
	cfg.Tracer = tracer

	txLogger, err := vm.NewTxLogger(
		types.MakeSigner(p.config, header.Number),
		p.config.IsLondon(blockNumber),
		header.BaseFee,
		block.Hash(),
		block.NumberU64(), 100000, 1000)
	if err != nil {
		return nil, nil, 0, fmt.Errorf("create tx logger failed: %w", err)
	}

	// Mutate the block and state according to any hard-fork specs
	if p.config.DAOForkSupport && p.config.DAOForkBlock != nil && p.config.DAOForkBlock.Cmp(block.Number()) == 0 {
		misc.ApplyDAOHardFork(statedb)
	}
	blockContext := NewEVMBlockContext(header, p.bc, nil)
	vmenv := vm.NewEVM(blockContext, vm.TxContext{}, statedb, p.config, cfg)
	// Iterate over and process the individual transactions
	var totalts time.Duration = 0.0
	for i, tx := range block.Transactions() {
		parityLogContext.TxPos = i
		parityLogContext.TxHash = tx.Hash()
		msg, err := tx.AsMessage(types.MakeSigner(p.config, header.Number), header.BaseFee)
		if err != nil {
			return nil, nil, 0, fmt.Errorf("could not apply tx %d [%v]: %w", i, tx.Hash().Hex(), err)
		}
		statedb.Prepare(tx.Hash(), i)
		receipt, err := applyTransaction(msg, p.config, p.bc, nil, gp, statedb, blockNumber, blockHash, tx, usedGas, vmenv)
		if err != nil {
			return nil, nil, 0, fmt.Errorf("could not apply tx %d [%v]: %w", i, tx.Hash().Hex(), err)
		}

		txstart := time.Now()
		if err := txLogger.Dump(i, tx, receipt); err != nil {
			return nil, nil, 0, fmt.Errorf("could not dump tx %d [%v] logger: %w", i, tx.Hash().Hex(), err)
		}

		totalts += time.Since(txstart)

		receipts = append(receipts, receipt)
		allLogs = append(allLogs, receipt.Logs...)
	}
	fmt.Printf("Dump transaction, block_number = %v ,cost time = %v\n", strconv.FormatUint(block.NumberU64(), 10), totalts.Seconds())

	stateSyncTxHash := types.GetDerivedBorTxHash(types.BorReceiptKey(block.NumberU64(), block.Hash()))
	parityLogContext.TxPos = len(block.Transactions())
	parityLogContext.TxHash = stateSyncTxHash

	// Finalize the block, applying any consensus engine specific extras (e.g. block rewards)
	p.engine.Finalize(p.bc, header, statedb, block.Transactions(), block.Uncles())
	receiptsToDump := receipts

	// feat(trace): Check whether state sync happens.
	// Have to hardcode bor.config.Sprint (i.e. 64), since that config is out of scope now.
	if block.NumberU64()%64 == 0 {
		blockLogs := statedb.Logs()
		if len(blockLogs) > 0 {
			sort.SliceStable(blockLogs, func(i, j int) bool {
				return blockLogs[i].Index < blockLogs[j].Index
			})
			if len(blockLogs) > len(allLogs) {
				stateSyncLogs := blockLogs[len(allLogs):] // get state-sync logs from `state.Logs()`
				// State sync logs don't have tx index, tx hash and other necessary fields
				// DeriveFieldsForBorLogs will fill those fields for websocket subscriptions
				types.DeriveFieldsForBorLogs(stateSyncLogs, block.Hash(), block.NumberU64(), uint(len(receipts)), uint(len(allLogs)))
				index := len(block.Transactions())
				fmt.Printf(
					"Dump state sync txn %v: block number = %v, num_logs = %v",
					stateSyncTxHash.Hex(), strconv.FormatUint(block.NumberU64(), 10), len(stateSyncLogs),
				)
				if err := txLogger.DumpStateSyncTxn(index, stateSyncTxHash); err != nil {
					return nil, nil, 0, fmt.Errorf("could not dump state sync tx %d [%v] logger: %w", index, stateSyncTxHash.Hex(), err)
				}
				stateSyncReceipt := &types.Receipt{Logs: stateSyncLogs}
				receiptsToDump = append(append(types.Receipts{}, receipts...), stateSyncReceipt)
			}
		}
	}

	vm.ReceiptDumpLogger(block.NumberU64(), 100000, 1000, receiptsToDump)
	vm.TryClearBuffer(block.NumberU64())
	return receipts, allLogs, *usedGas, nil
}

func applyTransaction(msg types.Message, config *params.ChainConfig, bc ChainContext, author *common.Address, gp *GasPool, statedb *state.StateDB, blockNumber *big.Int, blockHash common.Hash, tx *types.Transaction, usedGas *uint64, evm *vm.EVM) (*types.Receipt, error) {
	// Create a new context to be used in the EVM environment.
	txContext := NewEVMTxContext(msg)
	evm.Reset(txContext, statedb)

	// Apply the transaction to the current state (included in the env).
	result, err := ApplyMessage(evm, msg, gp)
	if err != nil {
		return nil, err
	}

	// Update the state with pending changes.
	var root []byte
	if config.IsByzantium(blockNumber) {
		statedb.Finalise(true)
	} else {
		root = statedb.IntermediateRoot(config.IsEIP158(blockNumber)).Bytes()
	}
	*usedGas += result.UsedGas

	// Create a new receipt for the transaction, storing the intermediate root and gas used
	// by the tx.
	receipt := &types.Receipt{Type: tx.Type(), PostState: root, CumulativeGasUsed: *usedGas}
	if result.Failed() {
		receipt.Status = types.ReceiptStatusFailed
	} else {
		receipt.Status = types.ReceiptStatusSuccessful
	}
	receipt.TxHash = tx.Hash()
	receipt.GasUsed = result.UsedGas

	// If the transaction created a contract, store the creation address in the receipt.
	if msg.To() == nil {
		receipt.ContractAddress = crypto.CreateAddress(evm.TxContext.Origin, tx.Nonce())
	}

	// Set the receipt logs and create the bloom filter.
	receipt.Logs = statedb.GetLogs(tx.Hash(), blockHash)
	receipt.Bloom = types.CreateBloom(types.Receipts{receipt})
	receipt.BlockHash = blockHash
	receipt.BlockNumber = blockNumber
	receipt.TransactionIndex = uint(statedb.TxIndex())
	return receipt, err
}

// ApplyTransaction attempts to apply a transaction to the given state database
// and uses the input parameters for its environment. It returns the receipt
// for the transaction, gas used and an error if the transaction failed,
// indicating the block was invalid.
func ApplyTransaction(config *params.ChainConfig, bc ChainContext, author *common.Address, gp *GasPool, statedb *state.StateDB, header *types.Header, tx *types.Transaction, usedGas *uint64, cfg vm.Config) (*types.Receipt, error) {
	msg, err := tx.AsMessage(types.MakeSigner(config, header.Number), header.BaseFee)
	if err != nil {
		return nil, err
	}
	// Create a new context to be used in the EVM environment
	blockContext := NewEVMBlockContext(header, bc, author)
	vmenv := vm.NewEVM(blockContext, vm.TxContext{}, statedb, config, cfg)
	return applyTransaction(msg, config, bc, author, gp, statedb, header.Number, header.Hash(), tx, usedGas, vmenv)
}
