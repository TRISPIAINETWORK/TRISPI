/**
 * TRISPI SDK — TypeScript client for TRISPI AI Blockchain
 * Token: TRP | Consensus: Proof of Intelligence (PoI)
 * Dual Runtime: EVM + WASM | Post-Quantum: Ed25519 + Dilithium3
 *
 * Install: npm install @trispi/sdk axios
 */
import axios, { AxiosInstance } from 'axios';

export interface Wallet {
  address: string;
  private_key: string;
  network: string;
  balance: number;
}

export interface Balance {
  address: string;
  balances: Record<string, number>;
  tokens: Array<{ symbol: string; name: string; balance: number; price_usd: number; value_usd: number }>;
}

export interface Transaction {
  tx_hash: string;
  sender: string;
  recipient: string;
  amount: number;
  block: number;
  timestamp: number;
}

export interface Tokenomics {
  genesis_supply: number;
  current_supply: number;
  total_burned: number;
  total_issued: number;
  is_deflationary: boolean;
  base_fee_burn_rate: number;
  priority_fee_rate: number;
}

export interface AIStatus {
  status: string;
  pytorch_available: boolean;
  model: string;
  accuracy: number;
  training_rounds: number;
  total_predictions: number;
  fraud_detected: number;
  mode: string;
}

export interface SystemMetrics {
  cpu: { cpu_count_physical: number; cpu_count_logical: number; cpu_percent: number };
  memory: { total_mb: number; available_mb: number; used_mb: number; percent: number };
  gpu: { available: boolean; name: string };
  energy: { total_watts: number; cpu_watts: number; gpu_watts: number; source: string };
  timestamp: number;
}

export interface NetworkStatus {
  status: string;
  block_height: number;
  total_blocks: number;
  peer_count: number;
  validator_count: number;
  chain_id: string;
}

export interface SwapQuote {
  from_token: string;
  to_token: string;
  amount_in: number;
  amount_out: number;
  rate: number;
  fee: number;
}

export interface SystemStatus {
  trispi_version: string;
  components: {
    python_ai_service: { status: string };
    go_consensus: { status: string; port: number; chain_length?: number };
    rust_core: { status: string; port: number; components?: string[] };
  };
}

export interface EnergyReading {
  device_id: string;
  api_key: string;
  power_watts: number;
  temperature_c: number;
  cpu_usage_pct: number;
  gpu_usage_pct: number;
  timestamp: number;
}

export class TrispiSDK {
  private client: AxiosInstance;

  /**
   * @param baseURL - TRISPI node URL (default: http://localhost:8000)
   */
  constructor(baseURL: string = 'http://localhost:8000') {
    this.client = axios.create({ baseURL, timeout: 10000 });
  }

  // ── Health ──────────────────────────────────────────────────────────────────

  async health(): Promise<{ status: string; service: string; version: string }> {
    const res = await this.client.get('/health');
    return res.data;
  }

  async systemStatus(): Promise<SystemStatus> {
    const res = await this.client.get('/api/system/status');
    return res.data;
  }

  // ── Wallet ──────────────────────────────────────────────────────────────────

  async createWallet(): Promise<Wallet> {
    const res = await this.client.get('/api/wallet/create');
    return res.data;
  }

  async getBalance(address: string): Promise<Balance> {
    const res = await this.client.get(`/api/wallet/balances/${address}`);
    return res.data;
  }

  async sendTransaction(sender: string, recipient: string, amount: number, privateKey?: string): Promise<Transaction> {
    const res = await this.client.post('/api/transaction/send', {
      sender, recipient, amount, private_key: privateKey
    });
    return res.data;
  }

  // ── Tokenomics ──────────────────────────────────────────────────────────────

  async getTokenomics(): Promise<Tokenomics> {
    const res = await this.client.get('/api/tokenomics');
    return res.data;
  }

  async getTokenPrice(symbol: string = 'TRP'): Promise<{ symbol: string; price_usd: number; name: string }> {
    const res = await this.client.get(`/api/dex/price/${symbol}`);
    return res.data;
  }

  // ── AI ──────────────────────────────────────────────────────────────────────

  async getAIStatus(): Promise<AIStatus> {
    const res = await this.client.get('/api/ai/status');
    return res.data;
  }

  async predictFraud(features: number[]): Promise<{ fraud_score: number; is_fraud: boolean; model: string }> {
    const res = await this.client.post('/ai/predict', { transaction: features });
    return res.data;
  }

  // ── Network ─────────────────────────────────────────────────────────────────

  async getNetworkOverview(): Promise<NetworkStatus> {
    const res = await this.client.get('/api/network/overview');
    return res.data;
  }

  async getNetworkStats(): Promise<Record<string, unknown>> {
    const res = await this.client.get('/api/network/stats');
    return res.data;
  }

  async getPQCStatus(): Promise<Record<string, unknown>> {
    const res = await this.client.get('/api/pqc/status');
    return res.data;
  }

  // ── Energy Provider ─────────────────────────────────────────────────────────

  async getSystemMetrics(): Promise<SystemMetrics> {
    const res = await this.client.get('/api/system/metrics');
    return res.data;
  }

  /**
   * Register a new energy-providing device.
   * Returns an api_key — store it securely, it cannot be recovered.
   */
  async registerEnergyDevice(params: {
    device_id: string;
    device_type: 'cpu' | 'gpu' | 'asic';
    cpu_cores: number;
    gpu_memory_mb?: number;
    wallet_address: string;
  }): Promise<{ api_key: string; device_id: string; registered: boolean }> {
    const res = await this.client.post('/api/energy/register', params);
    return res.data;
  }

  /**
   * Submit a power reading from your device.
   * Rewards are credited to your wallet_address at registration.
   */
  async submitEnergyReading(reading: EnergyReading): Promise<{ reward_trp: number; accepted: boolean }> {
    const res = await this.client.post('/api/energy/proxy/reading', reading);
    return res.data;
  }

  async getEnergyStatus(): Promise<Record<string, unknown>> {
    const res = await this.client.get('/api/energy/status');
    return res.data;
  }

  // ── DEX ─────────────────────────────────────────────────────────────────────

  async getDEXPools(): Promise<{ pools: unknown[] }> {
    const res = await this.client.get('/api/dex/pools');
    return res.data;
  }

  async getSwapQuote(fromToken: string, toToken: string, amount: number): Promise<SwapQuote> {
    const res = await this.client.get('/api/dex/quote', {
      params: { from_token: fromToken, to_token: toToken, amount }
    });
    return res.data;
  }

  async swap(fromToken: string, toToken: string, amount: number, trader: string): Promise<Record<string, unknown>> {
    const res = await this.client.post('/api/dex/swap', {
      from_token: fromToken, to_token: toToken, amount, trader
    });
    return res.data;
  }

  // ── Smart Contracts ─────────────────────────────────────────────────────────

  async deployContract(
    code: string,
    runtime: 'evm' | 'wasm' | 'hybrid',
    deployer: string,
    metadata?: Record<string, unknown>
  ): Promise<Record<string, unknown>> {
    const res = await this.client.post('/api/contracts/deploy', {
      code, runtime, deployer, metadata
    });
    return res.data;
  }

  async getContracts(): Promise<unknown[]> {
    const res = await this.client.get('/api/contracts');
    return res.data;
  }

  // ── Explorer ────────────────────────────────────────────────────────────────

  async getExplorerStats(): Promise<Record<string, unknown>> {
    const res = await this.client.get('/api/explorer/stats');
    return res.data;
  }

  async getRecentBlocks(limit: number = 10): Promise<{ blocks: unknown[]; total: number }> {
    const res = await this.client.get('/api/explorer/recent-blocks', { params: { limit } });
    return res.data;
  }

  async getRecentTransactions(limit: number = 20): Promise<{ transactions: unknown[]; total: number }> {
    const res = await this.client.get('/api/explorer/recent-transactions', { params: { limit } });
    return res.data;
  }

  async getBlock(blockNumber: number): Promise<Record<string, unknown>> {
    const res = await this.client.get(`/api/block/${blockNumber}`);
    return res.data;
  }

  // ── Governance ──────────────────────────────────────────────────────────────

  async getProposals(): Promise<unknown[]> {
    const res = await this.client.get('/api/governance/proposals');
    return res.data;
  }

  async createProposal(title: string, description: string, proposer: string): Promise<Record<string, unknown>> {
    const res = await this.client.post('/api/governance/proposals', {
      title, description, proposer
    });
    return res.data;
  }

  async vote(proposalId: string, voter: string, voteFor: boolean): Promise<Record<string, unknown>> {
    const res = await this.client.post('/api/governance/vote', {
      proposal_id: proposalId, voter, vote_for: voteFor
    });
    return res.data;
  }

  // ── Staking ─────────────────────────────────────────────────────────────────

  async stake(address: string, amount: number): Promise<Record<string, unknown>> {
    const res = await this.client.post('/api/staking/stake', { address, amount });
    return res.data;
  }

  async unstake(address: string, amount: number): Promise<Record<string, unknown>> {
    const res = await this.client.post('/api/staking/unstake', { address, amount });
    return res.data;
  }

  async getStakingInfo(address: string): Promise<Record<string, unknown>> {
    const res = await this.client.get(`/api/staking/info/${address}`);
    return res.data;
  }

  // ── Founder ─────────────────────────────────────────────────────────────────

  async getFounderWallet(): Promise<{
    address: string;
    evm_address: string;
    balance_trp: number;
    genesis_allocation: string;
  }> {
    const res = await this.client.get('/api/founder');
    return res.data;
  }
}

export default TrispiSDK;
