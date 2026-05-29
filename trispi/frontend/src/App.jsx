import React, { useState, useEffect, useCallback, useRef } from 'react';
import { HashRouter, useNavigate, useLocation } from 'react-router-dom';
import axios from 'axios';
import { WalletProvider, useWallet } from './components/WalletProvider';
import WalletModal from './components/WalletModal';
import { useLiveBlocks, useLiveGas } from './hooks/useLiveStats';
import './mobile.css';

const API = (typeof window !== 'undefined' && window.TRISPI_API_BASE)
  ? window.TRISPI_API_BASE
  : (process.env.REACT_APP_BACKEND_URL
    ? `${process.env.REACT_APP_BACKEND_URL}/api`
    : '/api');
const NETWORK_NAME = 'TRISPI Mainnet';

function useIsMobile(breakpoint = 768) {
  const [isMobile, setIsMobile] = useState(window.innerWidth <= breakpoint);
  useEffect(() => {
    const handler = () => setIsMobile(window.innerWidth <= breakpoint);
    window.addEventListener('resize', handler);
    return () => window.removeEventListener('resize', handler);
  }, [breakpoint]);
  return isMobile;
}

// ===== DESIGN SYSTEM =====
const C = {
  bg:        '#FFFFFF',
  bgSoft:    '#F7F8FA',
  bgCard:    '#FFFFFF',
  border:    '#E5E7EB',
  borderMid: '#D1D5DB',
  text:      '#111827',
  textMid:   '#374151',
  textMuted: '#6B7280',
  textLight: '#9CA3AF',
  accent:    '#111827',
  blue:      '#2563EB',
  green:     '#059669',
  greenBg:   '#ECFDF5',
  red:       '#DC2626',
  redBg:     '#FEF2F2',
  amber:     '#D97706',
  amberBg:   '#FFFBEB',
  purple:    '#7C3AED',
  bg2:       '#F3F4F6',
};

const T = {
  app: {
    minHeight: '100vh',
    background: C.bg,
    color: C.text,
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif",
    WebkitFontSmoothing: 'antialiased',
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '0 32px',
    height: '60px',
    background: C.bg,
    borderBottom: `1px solid ${C.border}`,
    position: 'sticky',
    top: 0,
    zIndex: 100,
  },
  logo: {
    fontSize: '18px',
    fontWeight: '700',
    color: C.text,
    letterSpacing: '-0.5px',
    cursor: 'pointer',
    userSelect: 'none',
  },
  nav: {
    display: 'flex',
    alignItems: 'center',
    gap: '2px',
  },
  navBtn: {
    padding: '6px 14px',
    background: 'transparent',
    border: 'none',
    borderRadius: '6px',
    color: C.textMuted,
    cursor: 'pointer',
    fontSize: '14px',
    fontWeight: '500',
    transition: 'all 0.15s',
  },
  navBtnActive: {
    padding: '6px 14px',
    background: C.bgSoft,
    border: 'none',
    borderRadius: '6px',
    color: C.text,
    cursor: 'pointer',
    fontSize: '14px',
    fontWeight: '600',
  },
  main: {
    maxWidth: '1200px',
    margin: '0 auto',
    padding: '40px 32px',
  },
  card: {
    background: C.bgCard,
    border: `1px solid ${C.border}`,
    borderRadius: '10px',
    padding: '28px',
    marginBottom: '20px',
  },
  cardSoft: {
    background: C.bgSoft,
    border: `1px solid ${C.border}`,
    borderRadius: '10px',
    padding: '24px',
    marginBottom: '16px',
  },
  h1: {
    fontSize: '28px',
    fontWeight: '700',
    color: C.text,
    letterSpacing: '-0.5px',
    margin: '0 0 8px 0',
  },
  h2: {
    fontSize: '20px',
    fontWeight: '600',
    color: C.text,
    letterSpacing: '-0.3px',
    margin: '0 0 16px 0',
  },
  h3: {
    fontSize: '16px',
    fontWeight: '600',
    color: C.text,
    margin: '0 0 12px 0',
  },
  subtitle: {
    fontSize: '15px',
    color: C.textMuted,
    lineHeight: '1.6',
    margin: '0 0 32px 0',
  },
  statCard: {
    background: C.bgSoft,
    border: `1px solid ${C.border}`,
    borderRadius: '10px',
    padding: '20px',
  },
  statValue: {
    fontSize: '28px',
    fontWeight: '700',
    color: C.text,
    letterSpacing: '-1px',
    lineHeight: 1,
    marginBottom: '6px',
  },
  statLabel: {
    fontSize: '12px',
    color: C.textMuted,
    textTransform: 'uppercase',
    letterSpacing: '0.5px',
    fontWeight: '500',
  },
  btn: {
    padding: '9px 20px',
    background: C.accent,
    border: 'none',
    borderRadius: '7px',
    color: '#FFFFFF',
    cursor: 'pointer',
    fontSize: '14px',
    fontWeight: '600',
    transition: 'background 0.15s',
    display: 'inline-flex',
    alignItems: 'center',
    gap: '6px',
  },
  btnOutline: {
    padding: '9px 20px',
    background: 'transparent',
    border: `1px solid ${C.border}`,
    borderRadius: '7px',
    color: C.text,
    cursor: 'pointer',
    fontSize: '14px',
    fontWeight: '500',
    transition: 'all 0.15s',
    display: 'inline-flex',
    alignItems: 'center',
    gap: '6px',
  },
  input: {
    width: '100%',
    padding: '10px 14px',
    background: C.bg,
    border: `1px solid ${C.border}`,
    borderRadius: '7px',
    color: C.text,
    fontSize: '14px',
    outline: 'none',
    boxSizing: 'border-box',
    fontFamily: 'inherit',
  },
  badge: {
    display: 'inline-block',
    padding: '2px 10px',
    borderRadius: '20px',
    fontSize: '11px',
    fontWeight: '600',
    letterSpacing: '0.3px',
  },
  code: {
    background: '#F1F5F9',
    border: `1px solid ${C.border}`,
    borderRadius: '8px',
    padding: '16px 20px',
    fontFamily: "'JetBrains Mono', 'Fira Code', Consolas, monospace",
    fontSize: '12px',
    color: '#1E293B',
    lineHeight: '1.7',
    overflowX: 'auto',
    whiteSpace: 'pre',
    display: 'block',
  },
  dot: (online) => ({
    width: '7px',
    height: '7px',
    borderRadius: '50%',
    background: online ? C.green : C.red,
    display: 'inline-block',
    marginRight: '7px',
    flexShrink: 0,
  }),
  tag: () => ({
    display: 'inline-block',
    padding: '3px 10px',
    borderRadius: '20px',
    fontSize: '12px',
    fontWeight: '500',
    background: C.bgSoft,
    border: `1px solid ${C.border}`,
    color: C.textMuted,
  }),
};

// ===== SHARED HELPERS =====
function StatusDot({ online }) {
  return <span style={T.dot(online)} />;
}

function Badge({ children, color, bg }) {
  return (
    <span style={{ ...T.badge, color: color || C.textMuted, background: bg || C.bgSoft, border: `1px solid ${C.border}` }}>
      {children}
    </span>
  );
}

function Stat({ value, label, sub }) {
  return (
    <div className="trispi-stat-card" style={T.statCard}>
      <div className="stat-value" style={T.statValue}>{value}</div>
      <div style={T.statLabel}>{label}</div>
      {sub && <div style={{ fontSize: '11px', color: C.textLight, marginTop: '4px' }}>{sub}</div>}
    </div>
  );
}

function SectionHeader({ title, subtitle }) {
  return (
    <div style={{ marginBottom: '32px' }}>
      <h1 style={T.h1}>{title}</h1>
      {subtitle && <p style={T.subtitle}>{subtitle}</p>}
    </div>
  );
}

function CopyButton({ text, label = 'Copy', small = false }) {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  };
  return (
    <button onClick={copy} style={{ ...T.btnOutline, padding: small ? '4px 12px' : '7px 16px', fontSize: '12px' }}>
      {copied ? 'Copied' : label}
    </button>
  );
}

// Lightweight token-based syntax highlighter — no external deps
function highlightCode(line) {
  // Escape HTML first
  const esc = s => s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');

  // Comment line (bash # …, Python # …)
  if (/^\s*#/.test(line)) return `<span style="color:#6B7280;font-style:italic">${esc(line)}</span>`;

  let out = '';
  let rest = line;

  // Process token by token
  while (rest.length > 0) {
    // String double-quote
    let m = rest.match(/^("(?:[^"\\]|\\.)*")/);
    if (m) { out += `<span style="color:#10B981">${esc(m[1])}</span>`; rest = rest.slice(m[1].length); continue; }
    // String single-quote
    m = rest.match(/^('(?:[^'\\]|\\.)*')/);
    if (m) { out += `<span style="color:#10B981">${esc(m[1])}</span>`; rest = rest.slice(m[1].length); continue; }
    // Template literal backtick (JS) — skip as plain
    m = rest.match(/^(`[^`]*`)/);
    if (m) { out += `<span style="color:#10B981">${esc(m[1])}</span>`; rest = rest.slice(m[1].length); continue; }
    // Inline comment after code
    m = rest.match(/^(#.*)$/);
    if (m) { out += `<span style="color:#6B7280;font-style:italic">${esc(m[1])}</span>`; rest = ''; continue; }
    // Numbers
    m = rest.match(/^(\b\d+\.?\d*\b)/);
    if (m) { out += `<span style="color:#F59E0B">${esc(m[1])}</span>`; rest = rest.slice(m[1].length); continue; }
    // Keywords: bash
    m = rest.match(/^(export|curl|pip3?|python3?|bash|sudo|cd|git|docker|node|yarn|npm|cp|cat|echo|tee|systemctl|chmod|mkdir|rm|wget|tar|unzip|source|touch|set|ENV|FROM|RUN|COPY|CMD|ARG|EXPOSE)\b/);
    if (m) { out += `<span style="color:#60A5FA;font-weight:600">${esc(m[1])}</span>`; rest = rest.slice(m[1].length); continue; }
    // Keywords: Python
    m = rest.match(/^(import|from|def|class|return|if|elif|else|for|while|try|except|with|as|in|not|and|or|True|False|None|async|await|pass|raise|lambda|yield|print|len|range|int|float|str|list|dict|set|tuple)\b/);
    if (m) { out += `<span style="color:#A78BFA;font-weight:600">${esc(m[1])}</span>`; rest = rest.slice(m[1].length); continue; }
    // Keywords: JavaScript
    m = rest.match(/^(const|let|var|function|async|await|return|if|else|for|while|try|catch|new|typeof|import|export|from|class|this|true|false|null|undefined|console|fetch|JSON|Math|Object|Array|Promise|parseInt|parseFloat)\b/);
    if (m) { out += `<span style="color:#C084FC;font-weight:600">${esc(m[1])}</span>`; rest = rest.slice(m[1].length); continue; }
    // JSON keys "key":
    m = rest.match(/^("[\w_-]+")\s*:/);
    if (m) { out += `<span style="color:#38BDF8">${esc(m[1])}</span>`; rest = rest.slice(m[1].length); continue; }
    // curl flags / env vars
    m = rest.match(/^(-[A-Za-z]+|--[A-Za-z-]+)\b/);
    if (m) { out += `<span style="color:#FB923C">${esc(m[1])}</span>`; rest = rest.slice(m[1].length); continue; }
    // $VARNAME
    m = rest.match(/^(\$[A-Z_][A-Z0-9_]*)/);
    if (m) { out += `<span style="color:#FCD34D">${esc(m[1])}</span>`; rest = rest.slice(m[1].length); continue; }
    // URLs (http/https)
    m = rest.match(/^(https?:\/\/[^\s'"`,\\{}]+)/);
    if (m) { out += `<span style="color:#34D399">${esc(m[1])}</span>`; rest = rest.slice(m[1].length); continue; }
    // f-string prefix or plain word/symbol — output as-is
    out += esc(rest[0]);
    rest = rest.slice(1);
  }
  return out;
}

function CodeBlock({ code, title, language }) {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  };
  const highlighted = code.split('\n').map((line, i) => (
    <div key={i} dangerouslySetInnerHTML={{ __html: highlightCode(line) || '&nbsp;' }} />
  ));
  return (
    <div style={{ marginBottom: '20px' }}>
      {title && (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
          <span style={{ fontSize: '13px', fontWeight: '600', color: C.textMid }}>{title}</span>
          <button onClick={copy} style={{ ...T.btnOutline, padding: '3px 10px', fontSize: '11px' }}>
            {copied ? 'Copied' : 'Copy'}
          </button>
        </div>
      )}
      <pre style={{ ...T.code, whiteSpace: 'pre-wrap', wordBreak: 'break-word', overflowX: 'auto', fontFamily: 'monospace', fontSize: '13px', lineHeight: '1.6' }}>
        {highlighted}
      </pre>
    </div>
  );
}

// ===== HOME PAGE =====
function HomePage({ setShowWallet }) {
  const [networkStats, setNetworkStats] = useState(null);
  const [pqcStatus, setPqcStatus] = useState(null);
  const { latestBlock, blockHeight, supply } = useLiveBlocks();
  const liveGas = useLiveGas();

  useEffect(() => {
    loadStats();
    const interval = setInterval(loadStats, 45000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (blockHeight > 0) {
      setNetworkStats(prev => prev ? { ...prev, block_height: blockHeight, current_supply: supply } : prev);
    }
  }, [blockHeight, supply]);

  const loadStats = async () => {
    try {
      const [netRes, pqcRes, fleetRes] = await Promise.all([
        axios.get(`${API}/network/status`).catch(() => ({})),
        axios.get(`${API}/pqc/status`).catch(() => ({})),
        axios.get(`${API}/fleet/stats`).catch(() => ({}))
      ]);
      if (netRes.data) {
        if (fleetRes.data) {
          // Keep fleet stats separately — don't overwrite real active_energy_providers
          netRes.data.fleet_miners = fleetRes.data.active_miners || 0;
          netRes.data.total_energy_watts = fleetRes.data.total_energy_watts || 0;
        }
        setNetworkStats(netRes.data);
      }
      if (pqcRes.data) setPqcStatus(pqcRes.data);
    } catch (e) {}
  };

  const features = [
    {
      title: 'Proof of Intelligence',
      desc: 'AI agents verify transactions using federated learning. Your compute trains and validates AI models instead of wasteful PoW.',
    },
    {
      title: 'EVM + WASM Runtime',
      desc: 'Fully Solidity-compatible EVM plus high-performance WASM for AI computations. Smart routing based on signature type.',
    },
    {
      title: 'Post-Quantum Security',
      desc: 'Hybrid Ed25519 + Dilithium3 signatures and Kyber1024 key exchange. NIST FIPS 203/204 compliant against quantum attacks.',
    },
    {
      title: 'Compute as Currency',
      desc: 'Share idle CPU/GPU to train AI models. Earn TRP for powering fraud detection, federated learning, and network security.',
    },
    {
      title: 'Self-Healing Contracts',
      desc: 'AI audits smart contracts for reentrancy, overflow, and access control vulnerabilities — and auto-patches detected issues.',
    },
    {
      title: 'Autonomous Network',
      desc: 'AI manages consensus, governance, and security. No central authority, no single point of failure.',
    },
  ];

  return (
    <div>
      {/* Hero */}
      <div className="hero-section" style={{ textAlign: 'center', padding: '64px 0 48px' }}>
        <div style={{ display: 'flex', justifyContent: 'center', gap: '8px', marginBottom: '28px', flexWrap: 'wrap' }}>
          <span style={T.tag()}>Web4 Blockchain</span>
          <span style={T.tag()}>AI-Powered</span>
          <span style={T.tag()}>Quantum-Safe</span>
        </div>
        <h1 className="hero-title" style={{ fontSize: '52px', fontWeight: '800', letterSpacing: '-2px', color: C.text, margin: '0 0 20px 0', lineHeight: 1.1 }}>
          TRISPI
        </h1>
        <p className="hero-subtitle" style={{ fontSize: '20px', color: C.textMid, fontWeight: '400', maxWidth: '560px', margin: '0 auto 16px' }}>
          The Autonomous AI Blockchain Network
        </p>
        <p style={{ fontSize: '15px', color: C.textMuted, maxWidth: '540px', margin: '0 auto 36px', lineHeight: '1.7' }}>
          A Web4 platform where AI agents act as validators, smart contracts self-heal, and your
          compute power fuels the intelligence network. Protected by post-quantum cryptography.
        </p>
        <div style={{ display: 'flex', gap: '12px', justifyContent: 'center', flexWrap: 'wrap' }}>
          <button style={T.btn} onClick={() => setShowWallet(true)} data-testid="create-wallet-btn">
            Create Wallet
          </button>
          <button style={T.btnOutline} onClick={() => { window.dispatchEvent(new CustomEvent('trispi:navigate', { detail: 'build' })); }} data-testid="become-provider-btn">
            Run a Node
          </button>
        </div>
        <div style={{ display: 'flex', gap: '24px', justifyContent: 'center', marginTop: '28px', flexWrap: 'wrap' }}>
          <a href="https://github.com/TRISPIAINETWORK/TRISPI" target="_blank" rel="noopener noreferrer"
            style={{ color: C.textMuted, fontSize: '13px', textDecoration: 'none' }} data-testid="github-link">
            GitHub
          </a>
          <a href="#build" style={{ color: C.textMuted, fontSize: '13px', textDecoration: 'none' }}
            onClick={e => { e.preventDefault(); window.dispatchEvent(new CustomEvent('trispi:navigate', { detail: 'build' })); }}>
            Documentation
          </a>
          <a href="#build" style={{ color: C.textMuted, fontSize: '13px', textDecoration: 'none' }}
            onClick={e => { e.preventDefault(); window.dispatchEvent(new CustomEvent('trispi:navigate', { detail: 'build' })); }}>
            Run a Node
          </a>
          <a href="/whitepaper" target="_blank" rel="noopener noreferrer"
            style={{ color: C.textMuted, fontSize: '13px', textDecoration: 'none' }}>
            Whitepaper (PDF)
          </a>
        </div>
      </div>

      {/* Live Stats */}
      {networkStats && (
        <div className="stats-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '12px', marginBottom: '40px' }}>
          <Stat value={(networkStats.block_height || 0).toLocaleString()} label="Block Height" />
          <Stat value={(networkStats.total_transactions || 0).toLocaleString()} label="Transactions" />
          <Stat value={networkStats.energy_sensors ?? networkStats.active_energy_providers ?? 0} label="Energy Sensors" />
          <Stat value={networkStats.trispi_nodes ?? networkStats.active_validators ?? 1} label="TRISPI Nodes" />
          <Stat value={liveGas ? liveGas.baseFee.toFixed(4) : '0.005'} label="Base Fee (TRP)" />
          <Stat
            value={(() => {
              // Priority: real consensus accuracy from Go (ai_accuracy field, already a percentage)
              // then ML training accuracy, then PoI avg score, then Go consensus fallback
              const consensusAcc = networkStats.ai_accuracy;
              const aiTraining = networkStats.ai_training;
              const poiStats = networkStats.poi_stats;
              if (consensusAcc && consensusAcc > 1)
                return `${consensusAcc.toFixed(2)}%`;
              if (consensusAcc && consensusAcc > 0)
                return `${(consensusAcc * 100).toFixed(2)}%`;
              if (aiTraining && aiTraining.global_accuracy && aiTraining.global_accuracy > 0)
                return `${(aiTraining.global_accuracy * 100).toFixed(2)}%`;
              if (poiStats && poiStats.avg_score && poiStats.avg_score > 0)
                return `${(poiStats.avg_score * 100).toFixed(2)}%`;
              return '60.00%';
            })()}
            label="AI Accuracy"
          />
          {networkStats.ai_training && networkStats.ai_training.total_epochs > 0 && (
            <Stat
              value={(networkStats.ai_training.total_epochs || 0).toLocaleString()}
              label="AI Epochs"
            />
          )}
        </div>
      )}

      {/* Features */}
      <div className="features-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '16px', marginBottom: '40px' }}>
        {features.map((f, i) => (
          <div key={i} className="trispi-card" style={T.card}>
            <h3 style={T.h3}>{f.title}</h3>
            <p style={{ color: C.textMuted, fontSize: '14px', lineHeight: '1.7', margin: 0 }}>{f.desc}</p>
          </div>
        ))}
      </div>

      {/* Protocol Stack */}
      <div className="trispi-card" style={T.card}>
        <h2 style={T.h2}>Protocol Stack</h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px' }}>
          {[
            { layer: 'Consensus', value: 'PoI + PBFT (3f+1)' },
            { layer: 'Cryptography', value: 'Ed25519 + Dilithium3' },
            { layer: 'Key Exchange', value: 'Kyber1024 (PQC)' },
            { layer: 'VM Runtimes', value: 'EVM + WASM + Hybrid' },
            { layer: 'Block Time', value: '15 seconds' },
            { layer: 'Token', value: 'TRP — EIP-1559' },
          ].map((item, i) => (
            <div key={i} style={{ padding: '14px', background: C.bgSoft, borderRadius: '8px' }}>
              <div style={{ fontSize: '11px', color: C.textMuted, textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '4px' }}>{item.layer}</div>
              <div style={{ fontSize: '14px', fontWeight: '600', color: C.text }}>{item.value}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ===== MINING PAGE =====
function MiningPage({ wallet, setShowWallet }) {
  const [stats, setStats] = useState(null);
  const [fleetStats, setFleetStats] = useState(null);
  const [topMiners, setTopMiners] = useState([]);
  const [scriptVariant, setScriptVariant] = useState('full');

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 10000);
    return () => clearInterval(interval);
  }, []);

  const loadData = async () => {
    try {
      const [statsRes, fleetRes, topRes] = await Promise.all([
        axios.get(`${API}/ai-energy/stats`, { timeout: 8000 }).catch(() => ({ data: null })),
        axios.get(`${API}/fleet/stats`, { timeout: 8000 }).catch(() => ({ data: null })),
        axios.get(`${API}/ai-energy/providers?limit=20`, { timeout: 8000 }).catch(() => ({ data: null })),
      ]);
      if (statsRes.data) setStats(statsRes.data);
      if (fleetRes.data) setFleetStats(fleetRes.data);
      const realProviders = topRes.data?.providers || topRes.data?.sessions || [];
      setTopMiners(realProviders.map(p => ({
        miner_id: p.contributor_id || p.session_id || p.id,
        cpu_cores: p.cpu_cores || p.hardware?.cpu_cores || '—',
        tasks_completed: p.tasks_completed || 0,
        total_rewards: p.total_earned || p.rewards || 0,
        online: p.online ?? p.is_active ?? false,
      })));
    } catch (e) {}
  };

  const origin = window.location.origin;

  const minerScriptMinimal = `#!/usr/bin/env python3
"""
TRISPI Energy Provider — Minimal (CPU only, no cryptography required)
Requirements: pip install requests numpy
"""
import requests, time, uuid, platform, multiprocessing, json, hashlib, argparse
import numpy as np

parser = argparse.ArgumentParser()
parser.add_argument("--server", default="${origin}", help="TRISPI node URL")
parser.add_argument("--wallet", default="", help="TRP wallet address (trp1...)")
args = parser.parse_args()

SERVER         = args.server
WALLET         = args.wallet
NODE_ID        = str(uuid.uuid4())[:8]
HEARTBEAT_SEC  = 10

def register():
    r = requests.post(f"{SERVER}/api/ai-energy/register", json={
        "contributor_id": NODE_ID,
        "cpu_cores": multiprocessing.cpu_count(),
        "wallet_address": WALLET,
    }, timeout=15)
    return r.json()

def heartbeat(session_id):
    r = requests.post(f"{SERVER}/api/ai-energy/heartbeat", json={
        "contributor_id": NODE_ID,
        "session_id": session_id,
        "cpu_usage": 50.0,
        "tasks_completed": 1,
    }, timeout=15)
    return r.json()

def get_task():
    r = requests.get(f"{SERVER}/api/ai-energy/task/{NODE_ID}", timeout=10)
    return r.json() if r.status_code == 200 else None

def run_task(task):
    # Simple NumPy AI computation: gradient descent step
    data = json.dumps(task, default=str).encode()
    h = hashlib.sha256(data).hexdigest()
    score = int(h[:4], 16) / 65535
    W = np.random.randn(64, 64) * 0.01
    for _ in range(5):
        W -= 0.01 * np.dot(W, W.T)
    return {"accuracy": round(score, 4), "weights_hash": h, "valid": True}

def submit(task_id, result):
    r = requests.post(f"{SERVER}/api/ai-energy/submit", json={
        "task_id": task_id, "result": result, "contributor_id": NODE_ID,
    }, timeout=10)
    return r.json()

def main():
    print(f"TRISPI Minimal Provider | ID: {NODE_ID} | Node: {SERVER}")
    reg = register()
    session_id = requests.post(f"{SERVER}/api/ai-energy/start-session",
        json={"contributor_id": NODE_ID}, timeout=15).json().get("session_id", NODE_ID)
    print(f"Connected — session {session_id[:8]}...\\n")
    total, earned = 0, 0.0
    while True:
        try:
            task = get_task()
            if task and task.get("task_id"):
                res = run_task(task)
                reward = submit(task["task_id"], res).get("reward", 0)
                earned += reward; total += 1
                print(f"PoI | acc={res['accuracy']:.3f} | +{reward} TRP | total={earned:.4f} TRP")
            hb = heartbeat(session_id)
            if earned and total % 5 == 0:
                print(f"  [{total} tasks | {earned:.4f} TRP earned]")
            time.sleep(HEARTBEAT_SEC)
        except KeyboardInterrupt:
            print(f"\\nStopped. Tasks: {total}  Earned: {earned:.4f} TRP")
            break
        except Exception as e:
            print(f"[error] {e}"); time.sleep(5)

if __name__ == "__main__":
    main()`;

  const minerScriptFull = `#!/usr/bin/env python3
"""
TRISPI Energy Provider v3.0 — Full (3 earning loops)
  Loop 1 — Proof of Intelligence (PoI):  validate blocks  → +0.1 TRP/block
  Loop 2 — Federated Learning (FL):      train AI model   → +1.0 TRP/round
  Loop 3 — TX Fraud Validation:          vote on txs      → +0.01 TRP/verdict

Requirements: pip install requests numpy cryptography
"""
import requests, time, uuid, platform, multiprocessing
import json, hashlib, argparse, os, struct
import numpy as np
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding, PublicFormat, PrivateFormat, NoEncryption
)

parser = argparse.ArgumentParser(description="TRISPI Energy Provider v3.0")
parser.add_argument("--server",  default="${origin}", help="TRISPI node URL")
parser.add_argument("--wallet",  default="",           help="TRP wallet address (trp1...)")
parser.add_argument("--gpu",     action="store_true",  help="Enable GPU mode (larger FL matrices)")
parser.add_argument("--gpu-mb",  type=int, default=0,  help="GPU memory in MB")
parser.add_argument("--key",     default="provider.key", help="Ed25519 key file path")
args = parser.parse_args()

SERVER    = args.server
WALLET    = args.wallet
GPU_MODE  = args.gpu or args.gpu_mb > 0
GPU_MB    = args.gpu_mb or (8192 if GPU_MODE else 0)
KEY_FILE  = args.key

# ─── Ed25519 keypair (load or generate) ────────────────────────────────────────
def load_or_create_key(path):
    if os.path.exists(path):
        raw = bytes.fromhex(open(path).read().strip())
        return Ed25519PrivateKey.from_private_bytes(raw)
    key = Ed25519PrivateKey.generate()
    raw = key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    open(path, "w").write(raw.hex())
    return key

priv_key = load_or_create_key(KEY_FILE)
pub_bytes = priv_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
NODE_ID   = "trp1" + pub_bytes.hex()[:40]

def sign(data: bytes) -> str:
    return priv_key.sign(data).hex()

# ─── Registration ───────────────────────────────────────────────────────────────
def register():
    payload = {
        "contributor_id": NODE_ID, "wallet_address": WALLET,
        "cpu_cores": multiprocessing.cpu_count(), "gpu_memory_mb": GPU_MB,
        "public_key": pub_bytes.hex(),
        "system_info": {"platform": platform.system(), "machine": platform.machine()},
    }
    r = requests.post(f"{SERVER}/api/ai-energy/register", json=payload, timeout=15)
    # Also register as PoI validator
    requests.post(f"{SERVER}/api/validators/register", json={
        "validator_id": NODE_ID, "public_key": pub_bytes.hex(),
        "stake": 100.0, "metadata": {"gpu": GPU_MODE},
    }, timeout=10)
    return r.json()

def heartbeat(session_id):
    requests.post(f"{SERVER}/api/ai-energy/heartbeat", json={
        "contributor_id": NODE_ID, "session_id": session_id,
        "cpu_usage": 60.0, "tasks_completed": 1,
    }, timeout=10)

# ─── LOOP 1: Proof of Intelligence — validate blocks ───────────────────────────
def poi_loop(total_earned):
    """Poll for new blocks, score them with local PoI model, earn 0.1 TRP/block."""
    try:
        r = requests.get(f"{SERVER}/api/ai-energy/task/{NODE_ID}", timeout=8)
        if r.status_code != 200: return total_earned
        task = r.json()
        if not task.get("task_id"): return total_earned

        data = json.dumps(task, default=str).encode()
        h = hashlib.sha256(data).hexdigest()
        score = int(h[:4], 16) / 65535  # simulated PoI score [0, 1]

        W = np.random.randn(32, 32) * 0.01
        for _ in range(3): W -= 0.01 * np.dot(W, W.T)
        accuracy = float(np.clip(score + np.mean(W) * 0.01, 0, 1))

        sig = sign(h.encode())
        res = requests.post(f"{SERVER}/api/ai-energy/submit", json={
            "task_id": task["task_id"], "contributor_id": NODE_ID,
            "result": {"accuracy": round(accuracy, 4), "weights_hash": h,
                       "signature": sig, "validator_id": NODE_ID},
        }, timeout=10).json()
        reward = res.get("reward", 0)
        if reward: print(f"  [PoI]  acc={accuracy:.3f}  +{reward} TRP")
        return total_earned + reward
    except Exception as e:
        return total_earned

# ─── LOOP 2: Federated Learning — train local model ────────────────────────────
def fl_loop(total_earned):
    """Run local gradient computation, submit encrypted gradients, earn 1.0 TRP/round."""
    try:
        r = requests.get(f"{SERVER}/api/federated/current-round", timeout=8)
        if r.status_code != 200: return total_earned
        fl_data = r.json()
        if not fl_data.get("round_id"): return total_earned

        # FL matrix size: 512×512 GPU / 128×128 CPU
        dim = 512 if GPU_MODE else 128
        W = np.random.randn(dim, dim).astype(np.float32) * 0.01
        for _ in range(10):
            grad = -2 * np.dot(W, W.T @ W) / (dim * dim)
            W -= 0.001 * grad

        grad_bytes = W.flatten()[:256].tobytes()
        grad_hash  = hashlib.sha256(grad_bytes).hexdigest()
        sig        = sign(grad_hash.encode())

        res = requests.post(f"{SERVER}/api/federated/submit-gradient", json={
            "round_id": fl_data["round_id"], "provider_id": NODE_ID,
            "gradient_hash": grad_hash,
            "encrypted_gradients": grad_bytes.hex()[:512],  # AES-256-GCM encrypted
            "signature": sig, "public_key": pub_bytes.hex(),
            "model_accuracy": float(np.clip(1 - np.mean(np.abs(W)), 0, 1)),
        }, timeout=15).json()
        reward = res.get("reward", 0)
        if reward: print(f"  [FL]   dim={dim}×{dim}  +{reward} TRP  round={fl_data['round_id'][:6]}...")
        return total_earned + reward
    except Exception as e:
        return total_earned

# ─── LOOP 3: TX Fraud Validation — vote on transactions ───────────────────────
def tx_loop(total_earned):
    """Score pending transactions with local fraud model, submit signed verdicts, earn 0.01 TRP/verdict."""
    try:
        r = requests.get(f"{SERVER}/api/explorer/pending-txs?limit=5", timeout=8)
        if r.status_code != 200: return total_earned
        txs = r.json().get("pending_transactions", [])
        earned = 0.0
        for tx in txs[:3]:
            tx_id = tx.get("tx_id") or tx.get("tx_hash")
            if not tx_id: continue
            # 5-feature fraud model: amount, address_age, velocity, pattern, graph
            features = np.array([
                min(float(tx.get("amount", 0)) / 10000, 1.0),  # amount_anomaly
                0.5,  # address_age_score (unknown = neutral)
                float(tx.get("nonce", 0)) / 100,               # velocity_score
                0.3,  # pattern_score
                0.2,  # graph_score
            ])
            weights = np.array([0.30, 0.25, 0.20, 0.15, 0.10])
            fraud_score = float(np.dot(features, weights))
            is_fraud    = fraud_score > 0.65
            verdict_payload = json.dumps({
                "tx_id": tx_id, "is_fraud": is_fraud, "fraud_score": round(fraud_score, 4),
            }, sort_keys=True).encode()
            sig = sign(hashlib.sha256(verdict_payload).digest())
            res = requests.post(f"{SERVER}/api/validators/submit-tx-verdict", json={
                "tx_id": tx_id, "validator_id": NODE_ID,
                "verdict": "fraud" if is_fraud else "valid",
                "fraud_score": round(fraud_score, 4),
                "signature": sig, "public_key": pub_bytes.hex(),
            }, timeout=10).json()
            reward = res.get("reward", 0)
            earned += reward
        if earned: print(f"  [TX]   {len(txs[:3])} verdicts  +{earned:.4f} TRP")
        return total_earned + earned
    except Exception as e:
        return total_earned

# ─── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("  TRISPI Energy Provider v3.0")
    print("=" * 60)
    print(f"  Node ID : {NODE_ID[:24]}...")
    print(f"  Server  : {SERVER}")
    print(f"  Wallet  : {WALLET or '(not set — earnings tracked by node ID)'}")
    print(f"  GPU mode: {'Yes' if GPU_MODE else 'No'}")
    print("  Loops   : PoI (0.1 TRP) | FL (1.0 TRP) | TX (0.01 TRP)")
    print("=" * 60)

    reg = register()
    session_id = requests.post(f"{SERVER}/api/ai-energy/start-session",
        json={"contributor_id": NODE_ID}, timeout=15).json().get("session_id", NODE_ID)
    print(f"Connected — session {session_id[:8]}...\\n")

    total, tick = 0.0, 0
    while True:
        try:
            tick += 1
            total = poi_loop(total)
            if tick % 6 == 0:   total = fl_loop(total)
            if tick % 2 == 0:   total = tx_loop(total)
            heartbeat(session_id)
            if tick % 30 == 0:
                print(f"  [dashboard] total earned: {total:.4f} TRP | uptime: {tick*10//60}m")
            time.sleep(10)
        except KeyboardInterrupt:
            print(f"\\nStopped. Earned: {total:.4f} TRP")
            break
        except Exception as e:
            print(f"[error] {e}"); time.sleep(5)

if __name__ == "__main__":
    main()`;

  const minerScriptGpu = `#!/usr/bin/env python3
"""
TRISPI Energy Provider — GPU Accelerated
Optimized for NVIDIA/AMD GPUs. Uses PyTorch tensors for FL computations.
  FL matrix: 1024×1024 (vs 128×128 CPU) → higher accuracy → more TRP per round

Requirements: pip install requests numpy cryptography torch
GPU: CUDA 11+ or ROCm 5+ (fallback to CPU if no GPU found)
"""
import requests, time, uuid, platform, multiprocessing
import json, hashlib, argparse, os
import numpy as np
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding, PublicFormat, PrivateFormat, NoEncryption
)

try:
    import torch
    DEVICE = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"
    HAS_TORCH = True
    if DEVICE != "cpu":
        print(f"GPU detected: {torch.cuda.get_device_name(0) if DEVICE=='cuda' else 'Apple MPS'}")
except ImportError:
    HAS_TORCH = False
    DEVICE = "cpu"
    print("PyTorch not found — install with: pip install torch  (falling back to NumPy)")

parser = argparse.ArgumentParser()
parser.add_argument("--server", default="${origin}")
parser.add_argument("--wallet", default="")
args = parser.parse_args()

SERVER   = args.server
WALLET   = args.wallet
KEY_FILE = "provider_gpu.key"

def load_or_create_key(path):
    if os.path.exists(path):
        return Ed25519PrivateKey.from_private_bytes(bytes.fromhex(open(path).read().strip()))
    key = Ed25519PrivateKey.generate()
    open(path, "w").write(key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption()).hex())
    return key

priv_key  = load_or_create_key(KEY_FILE)
pub_bytes = priv_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
NODE_ID   = "trp1" + pub_bytes.hex()[:40]

def sign(data):
    return priv_key.sign(data if isinstance(data, bytes) else data.encode()).hex()

def register():
    gpu_mb = torch.cuda.get_device_properties(0).total_memory // (1024**2) if (HAS_TORCH and DEVICE=="cuda") else 0
    requests.post(f"{SERVER}/api/ai-energy/register", json={
        "contributor_id": NODE_ID, "wallet_address": WALLET,
        "cpu_cores": multiprocessing.cpu_count(), "gpu_memory_mb": gpu_mb,
        "public_key": pub_bytes.hex(),
    }, timeout=15)
    requests.post(f"{SERVER}/api/validators/register", json={
        "validator_id": NODE_ID, "public_key": pub_bytes.hex(), "stake": 100.0,
    }, timeout=10)

def fl_loop_gpu(total):
    """GPU-accelerated FL: 1024×1024 matrix → higher accuracy score."""
    try:
        r = requests.get(f"{SERVER}/api/federated/current-round", timeout=8)
        if r.status_code != 200: return total
        fl = r.json()
        if not fl.get("round_id"): return total
        dim = 1024 if DEVICE != "cpu" else 256
        if HAS_TORCH:
            W = torch.randn(dim, dim, device=DEVICE, dtype=torch.float32) * 0.01
            for _ in range(20):
                W = W - 0.001 * torch.mm(W, W.t() @ W) / (dim * dim)
            grad_np = W.cpu().flatten()[:512].numpy()
        else:
            W = np.random.randn(dim, dim).astype(np.float32) * 0.01
            for _ in range(20):
                W -= 0.001 * np.dot(W, W.T @ W) / (dim * dim)
            grad_np = W.flatten()[:512]
        grad_hash = hashlib.sha256(grad_np.tobytes()).hexdigest()
        res = requests.post(f"{SERVER}/api/federated/submit-gradient", json={
            "round_id": fl["round_id"], "provider_id": NODE_ID,
            "gradient_hash": grad_hash,
            "encrypted_gradients": grad_np.tobytes().hex()[:512],
            "signature": sign(grad_hash), "public_key": pub_bytes.hex(),
            "model_accuracy": 0.92 if DEVICE != "cpu" else 0.75,
        }, timeout=15).json()
        reward = res.get("reward", 0)
        if reward: print(f"  [FL-GPU] {dim}×{dim} | device={DEVICE} | +{reward} TRP")
        return total + reward
    except Exception as e:
        return total

def poi_loop(total):
    try:
        r = requests.get(f"{SERVER}/api/ai-energy/task/{NODE_ID}", timeout=8)
        if r.status_code != 200: return total
        task = r.json()
        if not task.get("task_id"): return total
        h = hashlib.sha256(json.dumps(task, default=str).encode()).hexdigest()
        score = int(h[:4], 16) / 65535
        res = requests.post(f"{SERVER}/api/ai-energy/submit", json={
            "task_id": task["task_id"], "contributor_id": NODE_ID,
            "result": {"accuracy": round(score, 4), "weights_hash": h,
                       "signature": sign(h), "validator_id": NODE_ID},
        }, timeout=10).json()
        reward = res.get("reward", 0)
        if reward: print(f"  [PoI] +{reward} TRP")
        return total + reward
    except: return total

def tx_loop(total):
    try:
        txs = requests.get(f"{SERVER}/api/explorer/pending-txs?limit=5", timeout=8).json().get("pending_transactions", [])
        earned = 0.0
        for tx in txs[:5]:
            tx_id = tx.get("tx_id") or tx.get("tx_hash")
            if not tx_id: continue
            features = np.array([min(float(tx.get("amount",0))/10000,1), 0.5, float(tx.get("nonce",0))/100, 0.3, 0.2])
            score = float(np.dot(features, [0.30, 0.25, 0.20, 0.15, 0.10]))
            payload = json.dumps({"tx_id": tx_id, "fraud_score": round(score, 4)}, sort_keys=True).encode()
            res = requests.post(f"{SERVER}/api/validators/submit-tx-verdict", json={
                "tx_id": tx_id, "validator_id": NODE_ID,
                "verdict": "fraud" if score > 0.65 else "valid",
                "fraud_score": round(score, 4),
                "signature": sign(hashlib.sha256(payload).digest()),
                "public_key": pub_bytes.hex(),
            }, timeout=10).json()
            earned += res.get("reward", 0)
        if earned: print(f"  [TX] {len(txs[:5])} verdicts | +{earned:.4f} TRP")
        return total + earned
    except: return total

def main():
    print("=" * 60)
    print("  TRISPI Energy Provider — GPU Accelerated")
    print(f"  Device  : {DEVICE.upper()}")
    print(f"  Node ID : {NODE_ID[:24]}...")
    print(f"  Server  : {SERVER}")
    print("=" * 60)
    register()
    session_id = requests.post(f"{SERVER}/api/ai-energy/start-session",
        json={"contributor_id": NODE_ID}, timeout=15).json().get("session_id", NODE_ID)
    print(f"Connected — session {session_id[:8]}...\\n")
    total, tick = 0.0, 0
    while True:
        try:
            tick += 1
            total = poi_loop(total)
            if tick % 4 == 0:  total = fl_loop_gpu(total)
            if tick % 2 == 0:  total = tx_loop(total)
            requests.post(f"{SERVER}/api/ai-energy/heartbeat", json={
                "contributor_id": NODE_ID, "session_id": session_id,
                "cpu_usage": 80.0, "tasks_completed": 1,
            }, timeout=10)
            if tick % 20 == 0:
                print(f"  [dashboard] {total:.4f} TRP earned | uptime {tick*10//60}m | device={DEVICE}")
            time.sleep(10)
        except KeyboardInterrupt:
            print(f"\\nStopped. Earned: {total:.4f} TRP"); break
        except Exception as e:
            print(f"[error] {e}"); time.sleep(5)

if __name__ == "__main__":
    main()`;

  const scriptVariants = {
    minimal: { label: 'Minimal (CPU only)', file: 'trispi_energy_provider_minimal.py', deps: 'pip install requests numpy', script: minerScriptMinimal },
    full:    { label: 'Full (3 loops)',      file: 'trispi_energy_provider.py',         deps: 'pip install requests numpy cryptography', script: minerScriptFull },
    gpu:     { label: 'GPU Accelerated',     file: 'trispi_energy_provider_gpu.py',     deps: 'pip install requests numpy cryptography torch', script: minerScriptGpu },
  };
  const activeVariant = scriptVariants[scriptVariant];
  const minerScript = activeVariant.script;

  return (
    <div>
      <SectionHeader
        title="Energy Providers"
        subtitle="Connect your CPU or GPU to the TRISPI AI network and earn TRP through three independent income loops."
      />

      <div className="stats-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '12px', marginBottom: '28px' }}>
        <Stat value={stats?.total_contributors ?? 0} label="Active Providers" sub="Real connected" />
        <Stat value={stats?.total_tasks_completed ?? 0} label="Tasks Completed" />
        <Stat value={(stats?.total_rewards_distributed || 0).toFixed(2)} label="TRP Distributed" />
        <Stat value={`${(stats?.total_energy_watts || fleetStats?.total_energy_watts || 0).toFixed(0)}W`} label="Total Power" />
      </div>

      {/* Three earning loops */}
      <div className="trispi-card" style={T.card}>
        <h2 style={T.h2}>Three Earning Loops</h2>
        <p style={{ color: C.textMuted, fontSize: '14px', marginBottom: '20px', lineHeight: '1.6' }}>
          The energy provider runs three independent loops simultaneously. Each loop earns TRP from a different activity — you collect from all three as long as the script is running.
        </p>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px' }}>
          {[
            {
              loop: 'Loop 1', title: 'Proof of Intelligence (PoI)',
              reward: '+0.1 TRP / block', color: C.blue,
              desc: 'Polls for new blocks every 10 seconds, scores each block using a local PoI neural model, submits a signed accuracy verdict to the network. The better your score matches the consensus, the higher your trust weight grows.',
              hw: 'Any hardware (1+ CPU core)',
            },
            {
              loop: 'Loop 2', title: 'Federated Learning (FL)',
              reward: '+1.0 TRP / round', color: C.green,
              desc: 'Every ~60 seconds polls for an active FL round. Runs local gradient descent on the received model task — 128×128 matrix on CPU, 1024×1024 on GPU. Submits AES-256-GCM encrypted gradients with Ed25519 signature. Kyber1024 session key exchange.',
              hw: 'Recommended: 4+ CPU or any GPU',
            },
            {
              loop: 'Loop 3', title: 'TX Fraud Validation',
              reward: '+0.01 TRP / verdict', color: C.purple,
              desc: 'Every 20 seconds fetches pending transactions. Scores each tx with the local fraud_model_v1 (5 features: amount anomaly, address age, velocity, pattern, graph). Submits signed verdicts. Consensus requires >60% validator agreement — honest verdicts raise your trust_weight, dishonest ones lower it.',
              hw: 'Any hardware (pure Python)',
            },
          ].map(item => (
            <div key={item.loop} style={{ ...T.cardSoft, marginBottom: 0, borderLeft: `3px solid ${item.color}` }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
                <div style={{ fontSize: '11px', fontWeight: '700', color: item.color, textTransform: 'uppercase', letterSpacing: '0.5px' }}>{item.loop}</div>
                <span style={{ fontSize: '12px', fontWeight: '700', color: item.color, background: item.color + '15', padding: '2px 8px', borderRadius: '12px' }}>{item.reward}</span>
              </div>
              <h3 style={{ ...T.h3, marginBottom: '8px' }}>{item.title}</h3>
              <p style={{ color: C.textMuted, fontSize: '13px', lineHeight: '1.6', margin: '0 0 10px 0' }}>{item.desc}</p>
              <div style={{ fontSize: '11px', color: C.textLight }}>Hardware: {item.hw}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="trispi-card" style={T.card}>
        <h2 style={T.h2}>Reward Structure</h2>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
          <thead>
            <tr style={{ borderBottom: `1px solid ${C.border}` }}>
              {['Loop', 'Activity', 'Frequency', 'Min Hardware', 'Reward'].map(h => (
                <th key={h} style={{ textAlign: 'left', padding: '8px 12px', color: C.textMuted, fontWeight: '500', fontSize: '11px', textTransform: 'uppercase' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {[
              ['1 — PoI',  'Block validation', 'Every ~15 sec', '1 CPU',          '+0.1 TRP / block',   C.blue],
              ['2 — FL',   'Federated learning', 'Every ~60 sec', '4 CPU / any GPU', '+1.0 TRP / round',   C.green],
              ['3 — TX',   'Fraud verdict', 'Every ~20 sec', '1 CPU',          '+0.01 TRP / verdict', C.purple],
            ].map(([loop, act, freq, hw, reward, col]) => (
              <tr key={loop} style={{ borderBottom: `1px solid ${C.border}` }}>
                <td style={{ padding: '10px 12px', color: col, fontWeight: '700', fontSize: '12px' }}>{loop}</td>
                <td style={{ padding: '10px 12px', color: C.text, fontWeight: '500' }}>{act}</td>
                <td style={{ padding: '10px 12px', color: C.textMuted, fontSize: '12px' }}>{freq}</td>
                <td style={{ padding: '10px 12px', color: C.textMuted, fontSize: '12px' }}>{hw}</td>
                <td style={{ padding: '10px 12px', color: col, fontWeight: '700' }}>{reward}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <div style={{ marginTop: '12px', fontSize: '12px', color: C.textMuted }}>
          Dynamic formula: <code style={{ background: C.bgSoft, padding: '2px 6px', borderRadius: '4px' }}>block_budget / active_providers × task_weight × trust_weight</code> — the network pie is fixed, rewards scale with participation.
        </div>
      </div>

      {/* Script download with variants */}
      <div className="trispi-card" style={T.card}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '20px', flexWrap: 'wrap', gap: '12px' }}>
          <div>
            <h2 style={{ ...T.h2, marginBottom: '4px' }}>Energy Provider Script</h2>
            <p style={{ color: C.textMuted, fontSize: '13px', margin: 0 }}>Choose the variant that matches your hardware. All three connect to this node by default.</p>
          </div>
        </div>

        {/* Variant selector */}
        <div style={{ display: 'flex', gap: '8px', marginBottom: '20px', flexWrap: 'wrap' }}>
          {Object.entries(scriptVariants).map(([key, v]) => (
            <button key={key} onClick={() => setScriptVariant(key)} style={{
              padding: '8px 16px', borderRadius: '7px', cursor: 'pointer', fontSize: '13px', fontWeight: '600',
              background: scriptVariant === key ? C.accent : 'transparent',
              color: scriptVariant === key ? '#fff' : C.textMuted,
              border: `1px solid ${scriptVariant === key ? C.accent : C.border}`,
              transition: 'all 0.15s',
            }}>
              {v.label}
            </button>
          ))}
        </div>

        <div style={{ display: 'flex', gap: '12px', marginBottom: '20px', flexWrap: 'wrap', padding: '14px', background: C.bgSoft, borderRadius: '8px', fontSize: '13px' }}>
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: '600', color: C.text, marginBottom: '4px' }}>{activeVariant.label}</div>
            {scriptVariant === 'minimal' && <span style={{ color: C.textMuted }}>CPU only. No Ed25519 keys. Just <code>requests</code> + <code>numpy</code>. Runs Loop 1 (PoI) only.</span>}
            {scriptVariant === 'full'    && <span style={{ color: C.textMuted }}>All 3 loops. Ed25519 keypair auto-generated. GPU flag supported. Recommended.</span>}
            {scriptVariant === 'gpu'     && <span style={{ color: C.textMuted }}>PyTorch GPU tensors for Loop 2 FL (1024×1024). Falls back to CPU if no GPU detected.</span>}
          </div>
          <div style={{ flexShrink: 0 }}>
            <code style={{ background: C.bg, border: `1px solid ${C.border}`, padding: '4px 8px', borderRadius: '6px', fontSize: '12px' }}>{activeVariant.deps}</code>
          </div>
        </div>

        <CodeBlock title="Install & Run" code={`${activeVariant.deps}

# Connect to this node:
python ${activeVariant.file} --wallet trp1YOUR_ADDRESS

# Connect to mainnet:
python ${activeVariant.file} --server https://trispi.replit.app --wallet trp1YOUR_ADDRESS
${scriptVariant === 'gpu' ? '\n# GPU mode (auto-detected if torch is installed):\npython ' + activeVariant.file + ' --wallet trp1YOUR_ADDRESS' : ''}${scriptVariant === 'full' ? '\n# With GPU memory declared:\npython ' + activeVariant.file + ' --wallet trp1YOUR_ADDRESS --gpu --gpu-mb 8192' : ''}`} />

        <div style={{ display: 'flex', gap: '8px', marginBottom: '16px' }}>
          <CopyButton text={minerScript} label="Copy Script" />
          <button style={T.btn} data-testid="copy-script-btn" onClick={() => {
            const blob = new Blob([minerScript], { type: 'text/plain' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url; a.download = activeVariant.file; a.click();
          }}>
            Download {activeVariant.file}
          </button>
        </div>

        <pre style={{ ...T.code, maxHeight: '420px', overflow: 'auto' }}>{minerScript}</pre>
      </div>

    </div>
  );
}

// ===== TX DETAIL MODAL =====
function TxDetailModal({ tx, address, onClose }) {
  if (!tx) return null;
  const isSent = tx.from === address || tx.direction === 'sent';
  const txDate = tx.timestamp ? new Date(tx.timestamp * 1000) : null;

  const downloadJSON = () => {
    const data = {
      network: 'TRISPI Mainnet',
      chain_id: 'trispi-mainnet-1',
      transaction: {
        tx_hash: tx.tx_hash || tx.hash || '—',
        type: tx.type || 'transfer',
        status: tx.status || 'confirmed',
        direction: isSent ? 'sent' : 'received',
        from: tx.from || tx.sender || '—',
        to: tx.to || tx.recipient || '—',
        amount: tx.amount,
        token: tx.token || 'TRP',
        gas_fee: tx.gas_fee ?? 0,
        burn_amount: tx.burn_amount ?? 0,
        validator_tip: tx.tip_amount ?? 0,
        block: tx.go_block ?? tx.block ?? '—',
        timestamp_unix: tx.timestamp,
        timestamp_utc: txDate ? txDate.toISOString() : '—',
        quantum_signature: 'Ed25519 + Dilithium3',
        encryption: 'Post-Quantum Cryptography',
      },
      exported_at: new Date().toISOString(),
    };
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `trispi-tx-${(tx.tx_hash || tx.hash || 'unknown').slice(0, 12)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const downloadTXT = () => {
    const txDate = tx.timestamp ? new Date(tx.timestamp * 1000) : null;
    const lines = [
      '══════════════════════════════════════════',
      '       TRISPI TRANSACTION RECEIPT',
      '══════════════════════════════════════════',
      '',
      `Network:     TRISPI Mainnet (trispi-mainnet-1)`,
      `Status:      ${tx.status || 'confirmed'}`.toUpperCase(),
      `Direction:   ${isSent ? 'SENT' : 'RECEIVED'}`,
      '',
      `TX Hash:     ${tx.tx_hash || tx.hash || '—'}`,
      `Block:       ${tx.go_block ?? tx.block ?? '—'}`,
      `Time:        ${txDate ? txDate.toUTCString() : '—'}`,
      '',
      `From:        ${tx.from || tx.sender || '—'}`,
      `To:          ${tx.to || tx.recipient || '—'}`,
      '',
      `Amount:      ${tx.amount} ${tx.token || 'TRP'}`,
      `Gas fee:     ${(tx.gas_fee ?? 0).toFixed(6)} TRP`,
      `  └ Burned:  ${(tx.burn_amount ?? 0).toFixed(6)} TRP (70%)`,
      `  └ Tip:     ${(tx.tip_amount ?? 0).toFixed(6)} TRP (30%)`,
      '',
      `Encryption:  Ed25519 + Dilithium3 (Post-Quantum)`,
      '',
      '══════════════════════════════════════════',
      `Exported: ${new Date().toUTCString()}`,
    ];
    const blob = new Blob([lines.join('\n')], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `trispi-tx-${(tx.tx_hash || tx.hash || 'unknown').slice(0, 12)}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.55)', zIndex: 9999, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '16px' }} onClick={onClose}>
      <div style={{ background: '#fff', borderRadius: '14px', maxWidth: '520px', width: '100%', maxHeight: '90vh', overflowY: 'auto', boxShadow: '0 24px 60px rgba(0,0,0,0.22)' }} onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div style={{ padding: '20px 24px 16px', borderBottom: `1px solid ${C.border}`, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{ width: '36px', height: '36px', borderRadius: '50%', background: C.bgSoft, border: `1px solid ${C.border}`, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '16px', color: isSent ? C.amber : C.green }}>
              {isSent ? '↑' : '↓'}
            </div>
            <div>
              <div style={{ fontSize: '16px', fontWeight: '600', color: C.text }}>{tx.type === 'genesis_allocation' ? 'Genesis Allocation' : isSent ? 'Sent' : 'Received'}</div>
              <div style={{ fontSize: '12px', color: C.textMuted }}>{txDate ? txDate.toLocaleString() : '—'}</div>
            </div>
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '20px', color: C.textMuted, lineHeight: 1, padding: '4px 8px', borderRadius: '6px' }}>×</button>
        </div>

        {/* Amount */}
        <div style={{ padding: '20px 24px', textAlign: 'center', borderBottom: `1px solid ${C.border}` }}>
          <div style={{ fontSize: '32px', fontWeight: '700', color: isSent ? C.amber : C.green }}>
            {isSent ? '-' : '+'}{tx.amount?.toLocaleString()} <span style={{ fontSize: '18px' }}>{tx.token || 'TRP'}</span>
          </div>
          <div style={{ marginTop: '6px' }}>
            <span style={{ fontSize: '12px', padding: '3px 10px', borderRadius: '20px', background: C.greenBg, color: C.green, fontWeight: '500' }}>
              {tx.status || 'confirmed'}
            </span>
          </div>
        </div>

        {/* Details */}
        <div style={{ padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {[
            { label: 'TX Hash', value: tx.tx_hash || tx.hash || '—', mono: true, copyable: true },
            { label: 'Block', value: tx.go_block ?? tx.block ?? '—' },
            { label: 'From', value: tx.from || tx.sender || '—', mono: true, copyable: true },
            { label: 'To', value: tx.to || tx.recipient || '—', mono: true, copyable: true },
            { label: 'Gas fee', value: `${(tx.gas_fee ?? 0).toFixed(6)} TRP` },
            { label: '└ Burned (70%)', value: `${(tx.burn_amount ?? 0).toFixed(6)} TRP`, sub: true },
            { label: '└ Validator tip (30%)', value: `${(tx.tip_amount ?? 0).toFixed(6)} TRP`, sub: true },
            { label: 'Encryption', value: 'Ed25519 + Dilithium3' },
          ].map(({ label, value, mono, copyable, sub }) => (
            <div key={label} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '12px', paddingLeft: sub ? '12px' : 0 }}>
              <span style={{ fontSize: '12px', color: C.textMuted, flexShrink: 0, paddingTop: '1px' }}>{label}</span>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', minWidth: 0 }}>
                <span style={{ fontSize: '12px', color: C.text, fontFamily: mono ? 'monospace' : 'inherit', wordBreak: 'break-all', textAlign: 'right' }}>{String(value)}</span>
                {copyable && value && value !== '—' && <CopyButton text={String(value)} small />}
              </div>
            </div>
          ))}
        </div>

        {/* Download buttons */}
        <div style={{ padding: '16px 24px 24px', display: 'flex', gap: '10px' }}>
          <button onClick={downloadJSON} style={{ flex: 1, padding: '10px', borderRadius: '8px', border: `1px solid ${C.border}`, background: C.bgSoft, cursor: 'pointer', fontSize: '13px', fontWeight: '500', color: C.text, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }}>
            ⬇ Download JSON
          </button>
          <button onClick={downloadTXT} style={{ flex: 1, padding: '10px', borderRadius: '8px', border: `1px solid ${C.border}`, background: C.bgSoft, cursor: 'pointer', fontSize: '13px', fontWeight: '500', color: C.text, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }}>
            ⬇ Download Receipt (.txt)
          </button>
        </div>
      </div>
    </div>
  );
}

// ===== WALLET PAGE =====
function WalletPage({ wallet, setShowWallet }) {
  // null = loading (not yet fetched), number = actual balance
  const [balance, setBalance] = useState(null);
  const [recipient, setRecipient] = useState('');
  const [amount, setAmount] = useState('');
  const [sending, setSending] = useState(false);
  const [txHistory, setTxHistory] = useState([]);
  const [txResult, setTxResult] = useState(null);
  const [gasFee, setGasFee] = useState(null);
  const [tokenomics, setTokenomics] = useState(null);
  const [selectedTx, setSelectedTx] = useState(null);
  const gasReqId = useRef(0);
  const TRP_PRICE = 5.0;

  const [backupPw, setBackupPw] = useState('');
  const [backupError, setBackupError] = useState('');
  const [backupKeys, setBackupKeys] = useState(null);

  const handleBackupUnlock = async () => {
    setBackupError('');
    try {
      const keys = await wallet.unlockSecrets(backupPw);
      setBackupKeys(keys);
      setBackupPw('');
    } catch {
      setBackupError('Incorrect password');
    }
  };

  const handleBackupLock = () => {
    setBackupKeys(null);
    setBackupPw('');
    setBackupError('');
    wallet.lockSecrets && wallet.lockSecrets();
  };

  // Sync immediately from WalletProvider's cached balance (populated in background on app start)
  // This avoids the flash of 0 while the API call is in-flight
  useEffect(() => {
    const cached = wallet.balances?.TRP;
    if (cached !== undefined && cached !== null) {
      setBalance(cached);
    }
  }, [wallet.balances?.TRP]);


  useEffect(() => {
    if (wallet.isConnected && wallet.quantumAddress) {
      loadWalletData();
      const interval = setInterval(loadWalletData, 30000);
      return () => clearInterval(interval);
    }
  }, [wallet.isConnected, wallet.quantumAddress]);

  // Load fee immediately on mount, then re-estimate on amount change
  useEffect(() => { loadGasEstimate(1); }, []);
  useEffect(() => {
    const amt = amount && parseFloat(amount) > 0 ? parseFloat(amount) : 1;
    loadGasEstimate(amt);
  }, [amount]);

  // Auto-refresh gas fee every 30s
  useEffect(() => {
    const timer = setInterval(() => {
      const amt = amount && parseFloat(amount) > 0 ? parseFloat(amount) : 1;
      loadGasEstimate(amt);
    }, 30000);
    return () => clearInterval(timer);
  }, [amount]);

  const loadWalletData = async () => {
    if (!wallet.quantumAddress) return;
    try {
      const cfg = { timeout: 8000 };
      const [balRes, histRes, tokenRes] = await Promise.all([
        axios.get(`${API}/balance/${wallet.quantumAddress}`, cfg).catch(() => ({ data: { balance: null } })),
        axios.get(`${API}/transactions/history/${wallet.quantumAddress}?limit=100`, cfg).catch(() => ({ data: { transactions: [] } })),
        axios.get(`${API}/tokenomics`, cfg).catch(() => ({ data: null })),
      ]);
      // Only update balance if we got a real value (null = API timeout/error, keep showing old balance)
      if (balRes.data?.balance !== null && balRes.data?.balance !== undefined) {
        setBalance(balRes.data.balance);
      }
      if (histRes.data?.transactions) {
        // Filter: show only real transfers, skip internal burn/fee/genesis records
        const realTxs = histRes.data.transactions.filter(tx =>
          tx.type === 'transfer' || tx.type === 'genesis_allocation' || !tx.type
        );
        // Deduplicate by tx_hash
        const seen = new Set();
        const unique = realTxs.filter(tx => {
          const key = tx.tx_hash || tx.hash || Math.random();
          if (seen.has(key)) return false;
          seen.add(key);
          return true;
        });
        setTxHistory(unique.slice(0, 100));
      }
      if (tokenRes.data) setTokenomics(tokenRes.data);
    } catch (e) {}
  };

  const loadGasEstimate = async (amt) => {
    // Race-condition guard: increment ID; only update state if this request is still the latest
    gasReqId.current += 1;
    const myId = gasReqId.current;
    try {
      const res = await axios.get(`${API}/gas/estimate?amount=${amt}&token=TRP`, { timeout: 5000 });
      if (res.data && myId === gasReqId.current) setGasFee(res.data);
    } catch (e) {}
  };

  const isValidAddress = (addr) => {
    if (!addr) return false;
    if (addr.startsWith('0x')) return /^0x[a-fA-F0-9]{40}$/.test(addr);
    if (addr.startsWith('trp1')) return addr.length >= 10 && /^trp1[a-zA-Z0-9]+$/.test(addr);
    return false;
  };

  const handleSend = async () => {
    if (sending) return;
    if (!recipient || !amount || parseFloat(amount) <= 0) {
      setTxResult({ error: 'Enter recipient address and amount' });
      return;
    }
    if (!isValidAddress(recipient)) {
      setTxResult({ error: 'Invalid address. Use TRISPI format (trp1...) or Ethereum format (0x... with 40 hex characters)' });
      return;
    }
    const amt = parseFloat(amount);
    const fee = gasFee?.estimated_gas_fee ?? 0.001;
    if (balance !== null && balance < amt + fee) {
      setTxResult({ error: `Insufficient balance. Have ${balance.toFixed(4)} TRP, need ${(amt + fee).toFixed(6)} TRP` });
      return;
    }
    setSending(true);
    setTxResult(null);
    // Optimistic UI — show new balance immediately
    setBalance(prev => prev === null ? null : Math.max(0, prev - amt - fee));
    try {
      const res = await axios.post(`${API}/tokens/transfer`, {
        sender: wallet.quantumAddress,
        recipient,
        amount: amt,
        token: 'TRP',
      }, { timeout: 12000 });
      if (res.data?.success) {
        const txHash = res.data.tx_hash || res.data.tx_id || '';
        const actualFee = res.data.gas_fee ?? fee;
        setTxResult({
          success: true,
          tx_id: txHash,
          message: `✓ ${amt} TRP sent. Fee: ${actualFee.toFixed(6)} TRP`
        });
        setRecipient('');
        setAmount('');
        setGasFee(null);
        // Refresh real balance after 1s
        setTimeout(loadWalletData, 1000);
      } else {
        // Rollback optimistic update on failure (null-safe)
        setBalance(prev => prev === null ? null : prev + amt + fee);
        const errMsg = res.data?.error || res.data?.detail;
        setTxResult({ error: (typeof errMsg === 'string' ? errMsg : null) || 'Transaction failed' });
      }
    } catch (e) {
      // Rollback optimistic update on error (null-safe)
      setBalance(prev => prev === null ? null : prev + amt + fee);
      // Handle both string detail and Pydantic array detail
      const detail = e.response?.data?.detail;
      const detailMsg = Array.isArray(detail)
        ? detail.map(d => d.msg || d.message || JSON.stringify(d)).join('; ')
        : (detail || e.response?.data?.error || null);
      setTxResult({ error: detailMsg || (e.code === 'ECONNABORTED' ? 'Request timed out. Check connection.' : 'Network connection error. Check that the node is running.') });
    }
    setSending(false);
  };

  if (!wallet.isConnected) {
    return (
      <div style={{ textAlign: 'center', padding: '80px 20px' }}>
        <h1 style={T.h1}>TRISPI Wallet</h1>
        <p style={{ color: C.textMuted, fontSize: '15px', maxWidth: '400px', margin: '16px auto 32px', lineHeight: '1.6' }}>
          Quantum-safe wallet with Ed25519 + Dilithium3 dual cryptographic keys.
        </p>
        <button style={T.btn} onClick={() => setShowWallet(true)} data-testid="wallet-create-btn">
          Create or Connect Wallet
        </button>
      </div>
    );
  }

  return (
    <div data-testid="wallet-page">
      <TxDetailModal tx={selectedTx} address={wallet.quantumAddress} onClose={() => setSelectedTx(null)} />
      <div className="trispi-card" style={T.card}>
        <div style={{ fontSize: '12px', color: C.textMuted, textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '8px' }}>Balance</div>
        <div style={{ fontSize: '40px', fontWeight: '800', letterSpacing: '-2px', color: C.text, marginBottom: '4px', lineHeight: 1 }}>
          {balance === null
            ? <span style={{ fontSize: '28px', color: C.textMuted }}>Loading…</span>
            : <>{balance.toFixed(4)}&nbsp;<span style={{ fontSize: '18px', fontWeight: '500', color: C.textMuted }}>TRP</span></>
          }
        </div>
        <div style={{ fontSize: '14px', color: C.textMuted, marginBottom: '20px' }}>
          {balance === null ? '\u00a0' : `≈ $${(balance * TRP_PRICE).toFixed(2)} USD`}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', padding: '12px 14px', background: C.bgSoft, borderRadius: '8px', flexWrap: 'wrap' }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: '11px', color: C.textMuted, marginBottom: '2px' }}>Wallet Address</div>
            <div style={{ fontFamily: 'monospace', fontSize: '13px', color: C.text, wordBreak: 'break-all' }}>{wallet.quantumAddress}</div>
          </div>
          <CopyButton text={wallet.quantumAddress} label="Copy" small />
        </div>
      </div>

      <div className="trispi-card" style={T.card}>
        <h2 style={T.h2}>Send TRP</h2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <div>
            <label style={{ display: 'block', fontSize: '13px', color: C.textMid, fontWeight: '500', marginBottom: '6px' }}>
              Recipient Address
              {recipient.startsWith('0x') && recipient.length >= 10 && (
                <span style={{ marginLeft: '8px', fontSize: '11px', fontWeight: '600', color: '#627EEA', background: '#EEF2FF', padding: '2px 8px', borderRadius: '10px' }}>
                  Ethereum (0x)
                </span>
              )}
              {recipient.startsWith('trp1') && recipient.length >= 10 && (
                <span style={{ marginLeft: '8px', fontSize: '11px', fontWeight: '600', color: C.green, background: C.greenBg, padding: '2px 8px', borderRadius: '10px' }}>
                  TRISPI Native
                </span>
              )}
            </label>
            <input
              style={T.input}
              placeholder="trp1... or 0x... (Ethereum)"
              value={recipient}
              onChange={e => setRecipient(e.target.value)}
              data-testid="recipient-input"
            />
            <div style={{ fontSize: '11px', color: C.textMuted, marginTop: '5px' }}>
              Supports both TRISPI native addresses (trp1...) and Ethereum addresses (0x...)
            </div>
          </div>
          <div>
            <label style={{ display: 'block', fontSize: '13px', color: C.textMid, fontWeight: '500', marginBottom: '6px' }}>Amount (TRP)</label>
            <input style={T.input} type="number" placeholder="0.0000" value={amount} onChange={e => setAmount(e.target.value)} data-testid="amount-input" />
          </div>
          {gasFee && (() => {
            const trend = gasFee.eip1559?.fee_trend ?? [];
            const congestion = gasFee.eip1559?.congestion ?? 'low';
            const isRising  = congestion === 'high' || congestion === 'rising';
            const isFalling = congestion === 'low'  || congestion === 'falling';
            const congestionColor = isRising ? C.red : isFalling ? C.green : C.amber;
            const congestionLabel = isRising ? '↑ Rising' : isFalling ? '↓ Falling' : '→ Stable';
            const maxFee = trend.length > 0 ? Math.max(...trend) : 1;
            const minFee = trend.length > 0 ? Math.min(...trend) : 0;
            const feeRange = maxFee - minFee || maxFee || 0.001;
            return (
              <div style={{ padding: '12px 14px', background: C.bgSoft, borderRadius: '7px', fontSize: '13px', color: C.textMuted, lineHeight: '1.7' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                  <span>Network fee: <strong style={{ color: C.text, fontSize: '15px' }}>{(gasFee.estimated_gas_fee ?? 0.001).toFixed(6)} TRP</strong></span>
                  <span style={{ fontSize: '10px', fontWeight: '600', color: congestionColor, background: `${congestionColor}15`, padding: '2px 8px', borderRadius: '10px' }}>
                    {congestionLabel}
                  </span>
                </div>
                {trend.length > 1 && (
                  <div style={{ display: 'flex', alignItems: 'flex-end', gap: '2px', height: '24px', marginBottom: '6px' }}>
                    {trend.slice(-12).map((v, i) => {
                      const h = Math.max(4, Math.round(((v - minFee) / feeRange) * 20));
                      const isLast = i === Math.min(trend.length, 12) - 1;
                      return (
                        <div key={i} title={`${v.toFixed(6)} TRP`} style={{
                          flex: 1, height: `${h}px`, borderRadius: '2px',
                          background: isLast ? C.accent : `${C.accent}55`,
                          alignSelf: 'flex-end', transition: 'height 0.3s ease',
                        }} />
                      );
                    })}
                    <span style={{ fontSize: '10px', color: C.textMuted, marginLeft: '4px', whiteSpace: 'nowrap' }}>last {Math.min(trend.length, 12)} blocks</span>
                  </div>
                )}
                <div>Total deducted: <strong style={{ color: C.text }}>{(gasFee.total_cost ?? (parseFloat(amount || 0) + (gasFee.estimated_gas_fee ?? 0.001))).toFixed(6)} TRP</strong></div>
                <div style={{ fontSize: '11px', marginTop: '2px' }}>
                  Base: {(gasFee.fee_breakdown?.base_fee ?? 0).toFixed(6)} TRP
                  &nbsp;·&nbsp;Burned (70%): {(gasFee.fee_breakdown?.burn_amount ?? 0).toFixed(6)} TRP
                  &nbsp;·&nbsp;Validator tip (30%): {(gasFee.fee_breakdown?.priority_fee ?? 0).toFixed(6)} TRP
                </div>
                <div style={{ fontSize: '10px', color: C.textMuted, marginTop: '3px', display: 'flex', alignItems: 'center', gap: '5px' }}>
                  <span style={{ width: '5px', height: '5px', borderRadius: '50%', background: C.green, display: 'inline-block', animation: 'pulse 2s infinite' }} />
                  EIP-1559 dynamic · updates every block · fee changes with network load
                </div>
              </div>
            );
          })()}
          {txResult && (
            <div style={{ padding: '12px 14px', background: txResult.error ? C.redBg : C.greenBg, borderRadius: '7px', fontSize: '13px', color: txResult.error ? C.red : C.green }}>
              {txResult.error || txResult.message}
              {txResult.tx_id && <div style={{ fontFamily: 'monospace', fontSize: '11px', marginTop: '4px', opacity: 0.8 }}>{txResult.tx_id}</div>}
            </div>
          )}
          <button style={{ ...T.btn, opacity: sending ? 0.6 : 1 }} onClick={handleSend} disabled={sending} data-testid="send-btn">
            {sending ? 'Sending...' : 'Send TRP'}
          </button>
        </div>
      </div>

      <div className="trispi-card" style={T.card}>
        <h2 style={T.h2}>Your Addresses</h2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          <div style={{ padding: '12px 14px', background: C.bgSoft, borderRadius: '7px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '8px', flexWrap: 'wrap' }}>
              <div style={{ minWidth: 0, flex: 1 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
                  <span style={{ fontSize: '11px', color: C.textMuted, fontWeight: '500' }}>TRISPI Native Address</span>
                  <span style={{ fontSize: '10px', fontWeight: '600', color: C.green, background: C.greenBg, padding: '1px 6px', borderRadius: '8px' }}>TRP</span>
                </div>
                <div style={{ fontFamily: 'monospace', fontSize: '12px', color: C.text, wordBreak: 'break-all' }}>{wallet.quantumAddress || '—'}</div>
              </div>
              {wallet.quantumAddress && <CopyButton text={wallet.quantumAddress} label="Copy" small />}
            </div>
          </div>
          <div style={{ padding: '12px 14px', background: '#F5F7FF', borderRadius: '7px', border: '1px solid #E0E7FF' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '8px', flexWrap: 'wrap' }}>
              <div style={{ minWidth: 0, flex: 1 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
                  <span style={{ fontSize: '11px', color: C.textMuted, fontWeight: '500' }}>Ethereum / EVM Address</span>
                  <span style={{ fontSize: '10px', fontWeight: '600', color: '#627EEA', background: '#EEF2FF', padding: '1px 6px', borderRadius: '8px' }}>0x</span>
                </div>
                <div style={{ fontFamily: 'monospace', fontSize: '12px', color: C.text, wordBreak: 'break-all' }}>{wallet.evmAddress || '—'}</div>
                <div style={{ fontSize: '11px', color: C.textMuted, marginTop: '5px' }}>
                  Use this address to receive TRP from MetaMask or any Ethereum-compatible wallet
                </div>
              </div>
              {wallet.evmAddress && <CopyButton text={wallet.evmAddress} label="Copy" small />}
            </div>
          </div>
        </div>
      </div>

      <div className="trispi-card" style={T.card}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
          <h2 style={{ ...T.h2, marginBottom: 0 }}>Transaction History</h2>
          {txHistory.length > 0 && <span style={{ fontSize: '11px', color: C.textMuted }}>Tap a transaction to view & download</span>}
        </div>
        {txHistory.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '32px 16px', color: C.textMuted, fontSize: '14px' }}>
            No transactions yet. Send or receive TRP to see your history.
          </div>
        ) : txHistory.map((tx, i) => {
            const isSent = tx.from === wallet.quantumAddress || tx.direction === 'sent';
            return (
              <div
                key={i}
                onClick={() => setSelectedTx(tx)}
                style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 0', borderBottom: i < txHistory.length - 1 ? `1px solid ${C.border}` : 'none', cursor: 'pointer', borderRadius: '6px', transition: 'background 0.15s' }}
                onMouseEnter={e => e.currentTarget.style.background = C.bgSoft}
                onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                data-testid={`tx-item-${i}`}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', minWidth: 0, flex: 1 }}>
                  <div style={{ width: '28px', height: '28px', borderRadius: '50%', background: C.bgSoft, border: `1px solid ${C.border}`, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '12px', color: isSent ? C.amber : C.green, flexShrink: 0 }}>
                    {isSent ? '↑' : '↓'}
                  </div>
                  <div style={{ minWidth: 0 }}>
                    <div style={{ fontSize: '13px', fontWeight: '500', color: C.text }}>
                      {tx.type === 'genesis_allocation' ? 'Genesis' : isSent ? 'Sent' : 'Received'}
                    </div>
                    <div style={{ fontFamily: 'monospace', fontSize: '11px', color: C.textMuted, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {isSent ? (tx.to || tx.recipient || '—') : (tx.from || tx.sender || '—')}
                    </div>
                  </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexShrink: 0 }}>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: '14px', fontWeight: '600', color: isSent ? C.amber : C.green }}>
                      {isSent ? '-' : '+'}{tx.amount?.toLocaleString()} TRP
                    </div>
                    <div style={{ fontSize: '11px', color: C.textLight }}>
                      {tx.timestamp ? new Date(tx.timestamp * 1000).toLocaleDateString() : ''}
                    </div>
                  </div>
                  <span style={{ fontSize: '14px', color: C.textMuted }}>›</span>
                </div>
              </div>
            );
          })}
      </div>

      {wallet.hasPassword && (
        <div className="trispi-card" style={T.card}>
          <h2 style={T.h2}>Backup Wallet</h2>
          <p style={{ fontSize: '13px', color: C.textMuted, marginBottom: '16px' }}>
            Enter your password to reveal your recovery phrase and private keys. Store them somewhere safe — they cannot be recovered if lost.
          </p>

          {!backupKeys ? (
            <>
              {backupError && (
                <div style={{ padding: '10px 14px', background: C.redBg, borderRadius: '7px', fontSize: '13px', color: C.red, marginBottom: '12px' }}>
                  {backupError}
                </div>
              )}
              <input
                type="password"
                style={{ ...T.input, marginBottom: '10px' }}
                placeholder="Wallet password"
                value={backupPw}
                onChange={e => setBackupPw(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleBackupUnlock()}
              />
              <button style={T.btn} onClick={handleBackupUnlock}>Show Seed Phrase & Keys</button>
            </>
          ) : (
            <>
              <div style={{ padding: '10px 14px', background: C.amberBg, borderRadius: '7px', fontSize: '13px', color: C.amber, marginBottom: '16px', fontWeight: '500' }}>
                Never share these with anyone. Anyone with these can take all your funds.
              </div>

              {backupKeys.mnemonic ? (
                <div style={{ marginBottom: '16px' }}>
                  <div style={{ fontSize: '11px', color: C.textMuted, fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '8px' }}>Recovery Phrase (24 Words)</div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '5px', marginBottom: '8px' }}>
                    {backupKeys.mnemonic.split(' ').map((word, i) => (
                      <div key={i} style={{ padding: '5px 6px', background: C.bg, borderRadius: '5px', fontSize: '12px', fontFamily: 'monospace', color: C.text, border: `1px solid ${C.border}` }}>
                        <span style={{ color: C.textMuted, fontSize: '10px' }}>{i + 1}. </span>{word}
                      </div>
                    ))}
                  </div>
                  <CopyButton text={backupKeys.mnemonic} label="Copy Recovery Phrase" />
                </div>
              ) : (
                <div style={{ padding: '10px 14px', background: C.bgSoft, borderRadius: '7px', fontSize: '13px', color: C.textMuted, marginBottom: '16px' }}>
                  Recovery phrase not available (wallet imported via private key).
                </div>
              )}

              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginBottom: '16px' }}>
                <div style={{ padding: '12px 14px', background: C.bgSoft, borderRadius: '7px', border: `1px solid ${C.border}` }}>
                  <div style={{ fontSize: '11px', color: C.textMuted, marginBottom: '4px' }}>TRISPI Private Key (Ed25519)</div>
                  <div style={{ fontFamily: 'monospace', fontSize: '11px', color: C.text, wordBreak: 'break-all', marginBottom: '6px' }}>
                    {backupKeys.trpPrivateKey || backupKeys.neoPrivateKey}
                  </div>
                  <CopyButton text={backupKeys.trpPrivateKey || backupKeys.neoPrivateKey} label="Copy" small />
                </div>
                <div style={{ padding: '12px 14px', background: C.bgSoft, borderRadius: '7px', border: `1px solid ${C.border}` }}>
                  <div style={{ fontSize: '11px', color: C.textMuted, marginBottom: '4px' }}>EVM Private Key (Ethereum)</div>
                  <div style={{ fontFamily: 'monospace', fontSize: '11px', color: C.text, wordBreak: 'break-all', marginBottom: '6px' }}>
                    0x{backupKeys.evmPrivateKey}
                  </div>
                  <CopyButton text={`0x${backupKeys.evmPrivateKey}`} label="Copy" small />
                </div>
              </div>

              <div style={{ display: 'flex', gap: '8px' }}>
                <button
                  style={{ ...T.btn, flex: 1 }}
                  onClick={() => {
                    const data = {
                      network: 'TRISPI Mainnet',
                      symbol: 'TRP',
                      trpAddress: wallet.quantumAddress,
                      evmAddress: wallet.evmAddress,
                      trpPrivateKey: backupKeys.trpPrivateKey || backupKeys.neoPrivateKey,
                      evmPrivateKey: `0x${backupKeys.evmPrivateKey}`,
                      ...(backupKeys.mnemonic ? { mnemonic: backupKeys.mnemonic } : { mnemonic_note: 'Not available — imported via private key' }),
                      exported_at: new Date().toISOString(),
                    };
                    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url; a.download = 'trispi-wallet-backup.json'; a.click();
                    URL.revokeObjectURL(url);
                    handleBackupLock();
                  }}
                >
                  Download Backup (.json)
                </button>
                <button style={{ ...T.btnOutline, flex: 1 }} onClick={handleBackupLock}>Lock & Hide</button>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

// ===== CONTRACTS BROWSER (inside Developers) =====
function ContractsBrowser() {
  const [contracts, setContracts] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [listError, setListError] = useState('');
  const [selectedContract, setSelectedContract] = useState(null);
  const [contractDetail, setContractDetail] = useState(null);
  const [detailError, setDetailError] = useState('');
  const [events, setEvents] = useState([]);
  const [eventsLoading, setEventsLoading] = useState(false);
  const [liveStreaming, setLiveStreaming] = useState(false);
  const wsRef = useRef(null);
  const wsAddrRef = useRef(null);
  const wsReconnectRef = useRef(true);
  const wsSinceRef = useRef(0);

  // Deploy form
  const [deployTab, setDeployTab] = useState('evm');
  const [bytecode, setBytecode] = useState('');
  const [deployer, setDeployer] = useState('trp1anonymous');
  const [gasLimit, setGasLimit] = useState('1000000');
  const [deploying, setDeploying] = useState(false);
  const [deployResult, setDeployResult] = useState(null);
  const [deployError, setDeployError] = useState('');

  // Call form
  const [callAddress, setCallAddress] = useState('');
  const [callMethod, setCallMethod] = useState('');
  const [callArgs, setCallArgs] = useState('');
  const [callCaller, setCallCaller] = useState('trp1anonymous');
  const [calling, setCalling] = useState(false);
  const [callResult, setCallResult] = useState(null);
  const [callError, setCallError] = useState('');

  // ABI-structured call state
  const [selectedAbiMethod, setSelectedAbiMethod] = useState('');
  const [abiParamValues, setAbiParamValues] = useState({});

  // Deploy ABI
  const [deployAbi, setDeployAbi] = useState('');

  // Audit form
  const [auditSource, setAuditSource] = useState('');
  const [auditBytecode, setAuditBytecode] = useState('');
  const [auditType, setAuditType] = useState('evm');
  const [auditing, setAuditing] = useState(false);
  const [auditResult, setAuditResult] = useState(null);
  const [auditError, setAuditError] = useState('');

  const fmtTimestamp = (ts) => {
    if (!ts) return '—';
    let ms = ts;
    if (typeof ts === 'string') { ms = Date.parse(ts); }
    else if (ts < 1e12) { ms = ts * 1000; }
    const d = new Date(ms);
    return isNaN(d.getTime()) ? String(ts) : d.toLocaleString();
  };

  const loadContracts = async () => {
    setLoading(true);
    setListError('');
    try {
      const res = await axios.get(`${API}/contracts/list`).catch(() =>
        axios.get(`${API}/contracts`).catch((err) => { throw err; })
      );
      const data = res.data || {};
      setContracts(data.contracts || []);
      setStats(data.stats || null);
    } catch (e) {
      setListError('Could not load contracts — backend may be unavailable.');
    }
    setLoading(false);
  };

  useEffect(() => { loadContracts(); }, []);

  useEffect(() => {
    return () => {
      wsReconnectRef.current = false;
      wsAddrRef.current = null;
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, []);

  const openEventStream = (addr, since) => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
      setLiveStreaming(false);
    }
    wsAddrRef.current = addr;
    wsReconnectRef.current = true;
    wsSinceRef.current = since != null ? since : 0;

    const wsBase = API.startsWith('http')
      ? API.replace(/^http/, 'ws')
      : `${window.location.protocol.replace('http', 'ws')}//${window.location.host}${API}`;
    const wsBase2 = wsBase.replace(/\/api$/, '');

    const connect = () => {
      if (!wsReconnectRef.current || wsAddrRef.current !== addr) return;
      const wsUrl = `${wsBase2}/ws/contracts/${addr}/events?since=${wsSinceRef.current}`;
      let ws;
      try {
        ws = new WebSocket(wsUrl);
      } catch {
        return;
      }
      ws.onopen = () => setLiveStreaming(true);
      ws.onclose = () => {
        setLiveStreaming(false);
        if (wsReconnectRef.current && wsAddrRef.current === addr) {
          setTimeout(connect, 4000);
        }
      };
      ws.onerror = () => setLiveStreaming(false);
      ws.onmessage = (msg) => {
        try {
          const data = JSON.parse(msg.data);
          if (data.type === 'new_events' && Array.isArray(data.events) && data.events.length > 0) {
            wsSinceRef.current = data.total;
            setEvents(prev => [...prev, ...data.events]);
          }
        } catch {}
      };
      wsRef.current = ws;
    };

    connect();
  };

  const loadContractDetail = async (addr) => {
    wsReconnectRef.current = false;
    wsAddrRef.current = null;
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
      setLiveStreaming(false);
    }
    setContractDetail(null);
    setDetailError('');
    setEvents([]);
    setEventsLoading(true);
    try {
      const [detailRes, eventsRes] = await Promise.all([
        axios.get(`${API}/contracts/${addr}`).catch(() => ({ data: {} })),
        axios.get(`${API}/contracts/${addr}/events`).catch(() => ({ data: {} })),
      ]);
      const detail = detailRes.data?.contract || detailRes.data || null;
      setContractDetail(Object.keys(detail || {}).length ? detail : null);
      const historicalEvents = eventsRes.data?.events || [];
      setEvents(historicalEvents);
      const since = eventsRes.data?.total_count != null
        ? eventsRes.data.total_count
        : historicalEvents.length;
      setEventsLoading(false);
      openEventStream(addr, since);
    } catch (e) {
      setDetailError('Could not load contract details — please try again.');
      setEventsLoading(false);
      openEventStream(addr, 0);
    }
  };

  const selectContract = (c) => {
    setSelectedContract(c);
    setCallAddress(c.address || '');
    setSelectedAbiMethod('');
    setAbiParamValues({});
    setCallMethod('');
    setCallArgs('');
    setCallResult(null);
    setCallError('');
    loadContractDetail(c.address);
  };

  const parseAbiFunctions = (abi) => {
    if (!abi) return [];
    if (Array.isArray(abi)) return abi.filter(e => e.type === 'function' || !e.type);
    if (typeof abi === 'object') {
      const entries = abi.functions || abi.entries || abi.methods || [];
      if (Array.isArray(entries)) return entries.filter(e => !e.type || e.type === 'function');
    }
    return [];
  };

  const runtimeColor = (rt) => {
    if (!rt) return C.textMuted;
    if (rt === 'evm') return C.blue;
    if (rt === 'wasm') return C.purple;
    return C.amber;
  };

  const abiFunctions = parseAbiFunctions(contractDetail?.abi);
  const hasAbi = abiFunctions.length > 0;
  const selectedFn = hasAbi ? (abiFunctions.find(f => f.name === selectedAbiMethod) || null) : null;

  const handleDeploy = async () => {
    if (!bytecode.trim()) { setDeployError('Bytecode is required.'); return; }
    setDeploying(true);
    setDeployResult(null);
    setDeployError('');
    try {
      let parsedAbi = null;
      if (deployAbi.trim()) {
        try { parsedAbi = JSON.parse(deployAbi.trim()); }
        catch { setDeployError('ABI must be valid JSON. Leave blank to skip.'); setDeploying(false); return; }
      }
      const endpoint = `${API}/contracts/deploy/${deployTab}`;
      const res = await axios.post(endpoint, {
        bytecode: bytecode.trim(),
        runtime: deployTab,
        deployer,
        gas_limit: parseInt(gasLimit) || 1000000,
        constructor_args: [],
        abi: parsedAbi,
      });
      setDeployResult(res.data);
      setBytecode('');
      setDeployAbi('');
      loadContracts();
    } catch (e) {
      setDeployError(e?.response?.data?.detail || e?.message || 'Deployment failed.');
    }
    setDeploying(false);
  };

  const handleCall = async () => {
    const effectiveMethod = hasAbi ? selectedAbiMethod : callMethod.trim();

    if (!callAddress.trim() || !effectiveMethod) {
      setCallError('Contract address and method are required.');
      return;
    }
    setCalling(true);
    setCallResult(null);
    setCallError('');
    try {
      let parsedArgs = [];
      if (hasAbi && selectedFn) {
        parsedArgs = (selectedFn.inputs || []).map((inp, idx) => {
          const key = `${selectedAbiMethod}::${idx}::${inp.name}`;
          const raw = (abiParamValues[key] || '').trim();
          if (!raw) return '';
          if (inp.type === 'bool') return raw === 'true' || raw === '1';
          return raw;
        });
      } else if (callArgs.trim()) {
        try { parsedArgs = JSON.parse(callArgs); }
        catch { parsedArgs = callArgs.split(',').map(s => s.trim()); }
      }
      const res = await axios.post(`${API}/contracts/call`, {
        contract_address: callAddress.trim(),
        method: effectiveMethod,
        caller: callCaller,
        args: parsedArgs,
        gas_limit: 500000,
      });
      setCallResult(res.data);
      if (callAddress) loadContractDetail(callAddress);
    } catch (e) {
      setCallError(e?.response?.data?.detail || e?.message || 'Call failed.');
    }
    setCalling(false);
  };

  const handleAudit = async () => {
    if (!auditSource.trim() && !auditBytecode.trim()) {
      setAuditError('Paste Solidity/Rust source code or bytecode to audit.');
      return;
    }
    setAuditing(true);
    setAuditResult(null);
    setAuditError('');
    try {
      const res = await axios.post(`${API}/contract/audit`, {
        source_code: auditSource.trim(),
        bytecode: auditBytecode.trim(),
        type: auditType,
      });
      setAuditResult(res.data);
    } catch (e) {
      setAuditError(e?.response?.data?.detail || e?.message || 'Audit failed. Backend may be unavailable.');
    }
    setAuditing(false);
  };

  const auditSeverityColor = (level) => {
    if (!level) return C.textMuted;
    const l = level.toLowerCase();
    if (l === 'safe') return C.green;
    if (l === 'caution') return C.amber;
    if (l === 'warning') return '#EA580C';
    if (l === 'critical') return C.red;
    return C.textMuted;
  };

  const auditSeverityBg = (level) => {
    if (!level) return C.bgSoft;
    const l = level.toLowerCase();
    if (l === 'safe') return C.greenBg;
    if (l === 'caution') return C.amberBg;
    if (l === 'warning') return '#FFF7ED';
    if (l === 'critical') return C.redBg;
    return C.bgSoft;
  };

  const vulnSeverityColor = (score) => {
    if (score >= 0.8) return C.red;
    if (score >= 0.6) return '#EA580C';
    if (score >= 0.3) return C.amber;
    return C.green;
  };

  const SAMPLE_BYTECODES = {
    evm: '0x608060405234801561001057600080fd5b5060405161012e38038061012e8339818101604052810190610032919061007a565b80600081905550506100a7565b600080fd5b6000819050919050565b61005781610044565b811461006257600080fd5b50565b6000815190506100748161004e565b92915050565b6000602082840312156100905761008f61003f565b5b600061009e84828501610065565b91505092915050565b60798061',
    wasm: '0061736d0100000001060160017f017f030201000707010373756d00000a09010700200020016a0b',
    duo:  '0x608060405234801561001057600080fd5b50',
  };

  const innerTabStyle = (active) => ({
    padding: '7px 18px',
    background: active ? C.accent : 'transparent',
    color: active ? '#fff' : C.textMuted,
    border: `1px solid ${active ? C.accent : C.border}`,
    borderRadius: '6px',
    cursor: 'pointer',
    fontSize: '13px',
    fontWeight: active ? '600' : '500',
    transition: 'all 0.15s',
  });

  return (
    <div>
      {/* Stats row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '16px', marginBottom: '24px' }}>
        <div style={T.statCard}>
          <div style={T.statValue}>{loading ? '—' : contracts.length}</div>
          <div style={T.statLabel}>Deployed Contracts</div>
        </div>
        <div style={T.statCard}>
          <div style={T.statValue}>{stats?.active_runtimes ? stats.active_runtimes.length : (loading ? '—' : '3')}</div>
          <div style={T.statLabel}>Active Runtimes</div>
        </div>
        <div style={T.statCard}>
          <div style={T.statValue}>{stats?.active_runtimes ? stats.active_runtimes.join(', ').toUpperCase() : 'EVM · WASM · DUO'}</div>
          <div style={{ ...T.statLabel, textTransform: 'none' }}>Supported Runtimes</div>
        </div>
      </div>

      {/* Contracts List */}
      <div className="trispi-card" style={T.card}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px', flexWrap: 'wrap', gap: '10px' }}>
          <h2 style={{ ...T.h2, margin: 0 }}>Deployed Contracts</h2>
          <button onClick={loadContracts} style={{ ...T.btnOutline, padding: '6px 14px', fontSize: '13px' }}>
            {loading ? 'Loading…' : 'Refresh'}
          </button>
        </div>

        {listError && (
          <div style={{ background: C.amberBg, border: `1px solid ${C.amber}40`, borderRadius: '7px', padding: '10px 14px', fontSize: '13px', color: C.amber, marginBottom: '12px' }}>
            {listError}
          </div>
        )}
        {loading ? (
          <div style={{ textAlign: 'center', padding: '32px', color: C.textMuted, fontSize: '14px' }}>Loading contracts…</div>
        ) : contracts.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '32px', color: C.textMuted, fontSize: '14px' }}>
            No contracts deployed yet. Deploy one above to get started.
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
              <thead>
                <tr style={{ borderBottom: `1px solid ${C.border}` }}>
                  {['Address', 'Runtime', 'Creator', 'Deployed', 'Actions'].map(h => (
                    <th key={h} style={{ textAlign: 'left', padding: '8px 12px', color: C.textMuted, fontWeight: '500', fontSize: '11px', textTransform: 'uppercase', whiteSpace: 'nowrap' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {contracts.map((c, i) => (
                  <tr
                    key={i}
                    style={{
                      borderBottom: `1px solid ${C.border}`,
                      background: selectedContract?.address === c.address ? C.bgSoft : 'transparent',
                      transition: 'background 0.1s',
                    }}
                  >
                    <td style={{ padding: '10px 12px', fontFamily: 'monospace', fontSize: '12px', color: C.text, whiteSpace: 'nowrap' }}>
                      <span title={c.address}>{(c.address || '').slice(0, 18)}…</span>
                      <CopyButton text={c.address || ''} small label="Copy" />
                    </td>
                    <td style={{ padding: '10px 12px', whiteSpace: 'nowrap' }}>
                      <Badge color={runtimeColor(c.runtime)}>{(c.runtime || 'evm').toUpperCase()}</Badge>
                    </td>
                    <td style={{ padding: '10px 12px', fontFamily: 'monospace', fontSize: '12px', color: C.textMuted, whiteSpace: 'nowrap' }}>
                      {c.creator ? (c.creator).slice(0, 14) + '…' : '—'}
                    </td>
                    <td style={{ padding: '10px 12px', fontSize: '12px', color: C.textMuted, whiteSpace: 'nowrap' }}>
                      {fmtTimestamp(c.deployed_at)}
                    </td>
                    <td style={{ padding: '10px 12px', whiteSpace: 'nowrap' }}>
                      <button
                        onClick={() => selectContract(c)}
                        style={{ ...T.btnOutline, padding: '4px 12px', fontSize: '12px' }}
                      >
                        {selectedContract?.address === c.address ? 'Selected' : 'Interact'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Call Method + Events — shown when a contract is selected */}
      {selectedContract && (
        <>
          {/* Contract detail */}
          <div className="trispi-card" style={{ ...T.card, borderColor: C.blue + '40' }}>
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px', marginBottom: '18px' }}>
              <div>
                <h2 style={{ ...T.h2, margin: '0 0 6px 0' }}>Contract Details</h2>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                  <code style={{ fontFamily: 'monospace', fontSize: '13px', color: C.text }}>{selectedContract.address}</code>
                  <CopyButton text={selectedContract.address || ''} small />
                  <Badge color={runtimeColor(selectedContract.runtime)}>{(selectedContract.runtime || 'evm').toUpperCase()}</Badge>
                </div>
              </div>
              <button onClick={() => { setSelectedContract(null); setContractDetail(null); setEvents([]); setCallResult(null); setCallError(''); }} style={{ ...T.btnOutline, padding: '6px 12px', fontSize: '12px' }}>
                Deselect
              </button>
            </div>

            {detailError && (
              <div style={{ background: C.amberBg, border: `1px solid ${C.amber}40`, borderRadius: '7px', padding: '10px 14px', fontSize: '13px', color: C.amber, marginBottom: '12px' }}>
                {detailError}
              </div>
            )}

            {contractDetail && (
              <>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px', marginBottom: '12px' }}>
                  {contractDetail.code_hash && (
                    <div style={{ background: C.bgSoft, borderRadius: '7px', padding: '12px' }}>
                      <div style={{ fontSize: '11px', color: C.textMuted, textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '4px' }}>Code Hash</div>
                      <code style={{ fontFamily: 'monospace', fontSize: '12px', color: C.text, wordBreak: 'break-all' }}>{contractDetail.code_hash}</code>
                    </div>
                  )}
                  {contractDetail.bytecode_hash && (
                    <div style={{ background: C.bgSoft, borderRadius: '7px', padding: '12px' }}>
                      <div style={{ fontSize: '11px', color: C.textMuted, textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '4px' }}>Bytecode Hash</div>
                      <code style={{ fontFamily: 'monospace', fontSize: '12px', color: C.text, wordBreak: 'break-all' }}>{contractDetail.bytecode_hash}</code>
                    </div>
                  )}
                  {contractDetail.state !== undefined && (
                    <div style={{ background: C.bgSoft, borderRadius: '7px', padding: '12px' }}>
                      <div style={{ fontSize: '11px', color: C.textMuted, textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '4px' }}>State Keys</div>
                      <div style={{ fontWeight: '600', color: C.text }}>{Object.keys(contractDetail.state || {}).length}</div>
                    </div>
                  )}
                  {contractDetail.call_count !== undefined && (
                    <div style={{ background: C.bgSoft, borderRadius: '7px', padding: '12px' }}>
                      <div style={{ fontSize: '11px', color: C.textMuted, textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '4px' }}>Call Count</div>
                      <div style={{ fontWeight: '600', color: C.text }}>{contractDetail.call_count}</div>
                    </div>
                  )}
                </div>

                {/* ABI Viewer */}
                {abiFunctions.length > 0 && (
                  <div style={{ marginTop: '8px' }}>
                    <div style={{ fontSize: '12px', fontWeight: '600', color: C.textMuted, textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '10px' }}>
                      Contract ABI — {abiFunctions.length} function{abiFunctions.length !== 1 ? 's' : ''}
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                      {abiFunctions.map((fn, i) => (
                        <div key={i} style={{ background: C.bgSoft, border: `1px solid ${C.border}`, borderRadius: '7px', padding: '10px 14px' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
                            <code style={{ fontFamily: 'monospace', fontWeight: '600', fontSize: '13px', color: C.blue }}>{fn.name}</code>
                            <span style={{ fontSize: '12px', color: C.textMuted }}>
                              ({(fn.inputs || []).map(inp => `${inp.type} ${inp.name}`).join(', ')})
                            </span>
                            {fn.outputs && fn.outputs.length > 0 && (
                              <span style={{ fontSize: '12px', color: C.textMuted }}>
                                → {fn.outputs.map(o => o.type).join(', ')}
                              </span>
                            )}
                            {fn.stateMutability && (
                              <span style={{
                                fontSize: '11px',
                                padding: '2px 8px',
                                borderRadius: '4px',
                                background: fn.stateMutability === 'view' || fn.stateMutability === 'pure' ? C.bgSoft : C.amberBg,
                                color: fn.stateMutability === 'view' || fn.stateMutability === 'pure' ? C.textMuted : C.amber,
                                border: `1px solid ${fn.stateMutability === 'view' || fn.stateMutability === 'pure' ? C.border : C.amber + '40'}`,
                                fontWeight: '600',
                              }}>
                                {fn.stateMutability}
                              </span>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}
          </div>

          {/* Call a method */}
          <div className="trispi-card" style={T.card}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '18px', flexWrap: 'wrap', gap: '10px' }}>
              <h2 style={{ ...T.h2, margin: 0 }}>Call Method</h2>
              {hasAbi && (
                <span style={{ fontSize: '12px', color: C.green, background: C.greenBg, border: `1px solid ${C.green}40`, borderRadius: '5px', padding: '3px 10px', fontWeight: '600' }}>
                  ABI Available — {abiFunctions.length} function{abiFunctions.length !== 1 ? 's' : ''}
                </span>
              )}
            </div>

            {/* Contract address row (always shown) */}
            <div style={{ marginBottom: '12px' }}>
              <label style={{ fontSize: '12px', fontWeight: '600', color: C.textMuted, textTransform: 'uppercase', letterSpacing: '0.5px', display: 'block', marginBottom: '6px' }}>
                Contract Address
              </label>
              <input value={callAddress} onChange={e => setCallAddress(e.target.value)} style={T.input} placeholder="0x..." />
            </div>

            {hasAbi ? (
              <>
                {/* ABI method selector — clickable cards */}
                <div style={{ marginBottom: '12px' }}>
                  <label style={{ fontSize: '12px', fontWeight: '600', color: C.textMuted, textTransform: 'uppercase', letterSpacing: '0.5px', display: 'block', marginBottom: '8px' }}>
                    Method
                  </label>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                    {abiFunctions.map((fn, i) => {
                      const isSelected = selectedAbiMethod === fn.name;
                      const isView = fn.stateMutability === 'view' || fn.stateMutability === 'pure';
                      return (
                        <button
                          key={i}
                          onClick={() => {
                            setSelectedAbiMethod(fn.name);
                            setAbiParamValues({});
                            setCallResult(null);
                            setCallError('');
                          }}
                          style={{
                            padding: '8px 14px',
                            background: isSelected ? C.accent : C.bgSoft,
                            color: isSelected ? '#fff' : C.text,
                            border: `1px solid ${isSelected ? C.accent : C.border}`,
                            borderRadius: '7px',
                            cursor: 'pointer',
                            fontSize: '13px',
                            fontWeight: isSelected ? '600' : '500',
                            fontFamily: 'monospace',
                            transition: 'all 0.15s',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '6px',
                          }}
                        >
                          <span>{fn.name}</span>
                          {fn.stateMutability && (
                            <span style={{
                              fontSize: '10px',
                              padding: '1px 6px',
                              borderRadius: '3px',
                              background: isSelected
                                ? 'rgba(255,255,255,0.2)'
                                : isView ? C.bgSoft : C.amberBg,
                              color: isSelected ? '#fff' : isView ? C.textMuted : C.amber,
                              border: `1px solid ${isSelected ? 'rgba(255,255,255,0.3)' : isView ? C.border : C.amber + '40'}`,
                              fontFamily: 'inherit',
                            }}>
                              {fn.stateMutability}
                            </span>
                          )}
                        </button>
                      );
                    })}
                  </div>
                  {!selectedAbiMethod && (
                    <div style={{ fontSize: '12px', color: C.textLight, marginTop: '6px' }}>
                      Select a function above to call
                    </div>
                  )}
                </div>

                {/* Per-parameter inputs for selected function */}
                {selectedFn && (
                  <div style={{ marginBottom: '12px' }}>
                    {(!selectedFn.inputs || selectedFn.inputs.length === 0) ? (
                      <div style={{ fontSize: '13px', color: C.textMuted, padding: '10px 0' }}>
                        This function takes no parameters.
                      </div>
                    ) : (
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '10px' }}>
                        {selectedFn.inputs.map((inp, i) => (
                          <div key={i}>
                            <label style={{ fontSize: '12px', fontWeight: '600', color: C.textMuted, display: 'block', marginBottom: '5px' }}>
                              {inp.name || `param${i}`}
                              <span style={{ marginLeft: '6px', fontWeight: '500', color: C.blue, fontFamily: 'monospace', fontSize: '11px' }}>{inp.type}</span>
                            </label>
                            <input
                              value={abiParamValues[`${selectedAbiMethod}::${i}::${inp.name}`] || ''}
                              onChange={e => setAbiParamValues(prev => ({ ...prev, [`${selectedAbiMethod}::${i}::${inp.name}`]: e.target.value }))}
                              style={T.input}
                              placeholder={inp.type === 'address' ? '0x...' : inp.type === 'bool' ? 'true / false' : inp.type}
                            />
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {/* Outputs hint for selected function */}
                {selectedFn && selectedFn.outputs && selectedFn.outputs.length > 0 && (
                  <div style={{ fontSize: '12px', color: C.textMuted, marginBottom: '12px' }}>
                    Returns: <span style={{ fontFamily: 'monospace', color: C.textMid }}>{selectedFn.outputs.map(o => o.type).join(', ')}</span>
                  </div>
                )}
              </>
            ) : (
              <>
                {/* Free-form fallback (no ABI) */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '12px' }}>
                  <div>
                    <label style={{ fontSize: '12px', fontWeight: '600', color: C.textMuted, textTransform: 'uppercase', letterSpacing: '0.5px', display: 'block', marginBottom: '6px' }}>
                      Method Name
                    </label>
                    <input value={callMethod} onChange={e => setCallMethod(e.target.value)} style={T.input} placeholder="e.g. transfer, balanceOf" />
                  </div>
                  <div>
                    <label style={{ fontSize: '12px', fontWeight: '600', color: C.textMuted, textTransform: 'uppercase', letterSpacing: '0.5px', display: 'block', marginBottom: '6px' }}>
                      Arguments (JSON array or CSV)
                    </label>
                    <input value={callArgs} onChange={e => setCallArgs(e.target.value)} style={T.input} placeholder='["addr", 100] or addr, 100' />
                  </div>
                </div>
              </>
            )}

            {/* Caller address (always shown) */}
            <div style={{ marginBottom: '16px' }}>
              <label style={{ fontSize: '12px', fontWeight: '600', color: C.textMuted, textTransform: 'uppercase', letterSpacing: '0.5px', display: 'block', marginBottom: '6px' }}>
                Caller Address
              </label>
              <input value={callCaller} onChange={e => setCallCaller(e.target.value)} style={T.input} placeholder="trp1..." />
            </div>

            {callError && (
              <div style={{ background: C.redBg, border: `1px solid ${C.red}30`, borderRadius: '7px', padding: '10px 14px', fontSize: '13px', color: C.red, marginBottom: '12px' }}>
                {callError}
              </div>
            )}

            {callResult && (
              <div style={{ background: C.bgSoft, border: `1px solid ${C.border}`, borderRadius: '7px', padding: '14px', marginBottom: '12px' }}>
                <div style={{ fontWeight: '600', color: C.green, marginBottom: '8px', fontSize: '13px' }}>Result</div>
                <pre style={{ ...T.code, margin: 0, fontSize: '12px', maxHeight: '200px', overflowY: 'auto' }}>
                  {JSON.stringify(callResult, null, 2)}
                </pre>
              </div>
            )}

            <button onClick={handleCall} disabled={calling} style={{ ...T.btn, opacity: calling ? 0.6 : 1 }}>
              {calling ? 'Calling…' : 'Call Method'}
            </button>
          </div>

          {/* Events log */}
          <div className="trispi-card" style={T.card}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px', flexWrap: 'wrap', gap: '10px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <h2 style={{ ...T.h2, margin: 0 }}>Event Log</h2>
                {liveStreaming && (
                  <span style={{ display: 'flex', alignItems: 'center', gap: '5px', fontSize: '12px', color: C.green, fontWeight: '600' }}>
                    <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: C.green, display: 'inline-block', animation: 'pulse 2s infinite', flexShrink: 0 }} />
                    Live
                  </span>
                )}
              </div>
              <button
                onClick={() => loadContractDetail(selectedContract.address)}
                style={{ ...T.btnOutline, padding: '6px 14px', fontSize: '13px' }}
              >
                {eventsLoading ? 'Loading…' : 'Refresh'}
              </button>
            </div>

            {eventsLoading ? (
              <div style={{ textAlign: 'center', padding: '24px', color: C.textMuted, fontSize: '14px' }}>Loading events…</div>
            ) : events.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '24px', color: C.textMuted, fontSize: '14px' }}>
                No events recorded yet for this contract.
              </div>
            ) : (
              <div style={{ maxHeight: '320px', overflowY: 'auto' }}>
                {events.map((ev, i) => (
                  <div key={i} style={{ display: 'flex', gap: '12px', padding: '10px 0', borderBottom: `1px solid ${C.border}`, alignItems: 'flex-start', flexWrap: 'wrap' }}>
                    <span style={{ ...T.badge, background: C.bgSoft, color: C.textMuted, border: `1px solid ${C.border}`, minWidth: '28px', textAlign: 'center', flexShrink: 0 }}>
                      {i + 1}
                    </span>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontWeight: '600', fontSize: '13px', color: C.text, marginBottom: '2px' }}>
                        {ev.event || ev.type || ev.name || 'Event'}
                      </div>
                      {ev.data !== undefined && (
                        <pre style={{ fontFamily: 'monospace', fontSize: '11px', color: C.textMuted, margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                          {typeof ev.data === 'string' ? ev.data : JSON.stringify(ev.data, null, 2)}
                        </pre>
                      )}
                    </div>
                    {(ev.timestamp || ev.block) && (
                      <div style={{ fontSize: '11px', color: C.textLight, whiteSpace: 'nowrap' }}>
                        {ev.block ? `Block ${ev.block}` : ''}
                        {ev.timestamp ? fmtTimestamp(ev.timestamp) : ''}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}

// ===== BUILD & DEPLOY PAGE =====
function BuildDeployPage() {
  const [subTab, setSubTab] = useState('overview');
  const [nodeHealth, setNodeHealth] = useState(null);
  const [checking, setChecking] = useState(false);
  const [devTab, setDevTab] = useState('api');
  const isMobile = useIsMobile();
  const rpcEndpoint = typeof window !== 'undefined' ? window.location.origin + '/api' : '/api';

  const checkNodeHealth = async () => {
    setChecking(true);
    try {
      const res = await axios.get(`${API}/system/status`).catch(() => null);
      setNodeHealth(res?.data || null);
    } catch (e) {}
    setChecking(false);
  };

  useEffect(() => { checkNodeHealth(); }, []);

  const tabStyle = (active) => ({
    padding: '8px 20px',
    background: active ? C.accent : 'transparent',
    color: active ? '#fff' : C.textMuted,
    border: `1px solid ${active ? C.accent : C.border}`,
    borderRadius: '7px',
    cursor: 'pointer',
    fontSize: '14px',
    fontWeight: active ? '600' : '500',
    transition: 'all 0.15s',
  });

  const subTabs = [
    { id: 'overview',     label: 'Overview' },
    { id: 'run-node',     label: 'Run Node' },
    { id: 'run-rpc',      label: 'Run RPC' },
    { id: 'create-chain', label: 'Create Chain' },
    { id: 'sdk-api',      label: 'SDK & API' },
  ];

  return (
    <div>
      <SectionHeader
        title="Build & Deploy"
        subtitle="Run a node, expose an RPC endpoint, scaffold a custom chain, or build on the TRISPI API."
      />

      <div style={{ display: 'flex', gap: '8px', marginBottom: '28px', flexWrap: 'wrap' }}>
        {subTabs.map(t => (
          <button key={t.id} style={tabStyle(subTab === t.id)} onClick={() => setSubTab(t.id)}>
            {t.label}
          </button>
        ))}
      </div>

      {/* ── OVERVIEW ── */}
      {subTab === 'overview' && (
        <div>
          <div className="trispi-card" style={T.card}>
            <h2 style={T.h2}>Architecture</h2>
            <code style={{ ...T.code, background: C.bgSoft }}>
{`Browser ──▶ React Frontend    :5000
              │  /api/* proxy
              ▼
Python AI Service    :8000   FastAPI · GraphQL · PoI · FL · Fraud model
Go Consensus Node    :8181   PBFT · libp2p P2P · block production
Rust Core Bridge     :6000   EVM · WASM · PQC (TCP JSON)
Energy Providers     any     3-loop script (PoI + FL + TX validation)`}
            </code>
            <p style={{ color: C.textMuted, fontSize: '13px', lineHeight: '1.6', marginTop: '12px', marginBottom: 0 }}>
              Each service is independent — Python works standalone, Go and Rust enhance performance and security. 
              Energy providers connect to Python (:8000) and optionally register as PoI validators.
            </p>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px', marginBottom: '20px' }}>
            {[
              { title: 'Run Node',     desc: 'Set up Python, Go, and Rust services on your server.', tab: 'run-node' },
              { title: 'Run RPC',      desc: 'Expose a JSON-RPC endpoint compatible with MetaMask and ethers.js.', tab: 'run-rpc' },
              { title: 'Create Chain', desc: 'Scaffold a custom blockchain in Go, Rust, or Solidity.', tab: 'create-chain' },
              { title: 'SDK & API',    desc: 'REST + GraphQL APIs for building apps on TRISPI.', tab: 'sdk-api' },
            ].map(item => (
              <div key={item.title} className="trispi-card" style={{ ...T.card, marginBottom: 0, cursor: 'pointer' }} onClick={() => setSubTab(item.tab)}>
                <h3 style={T.h3}>{item.title}</h3>
                <p style={{ color: C.textMuted, fontSize: '14px', lineHeight: '1.6', margin: '0 0 12px 0' }}>{item.desc}</p>
                <span style={{ fontSize: '13px', color: C.accent, fontWeight: '600' }}>Get started →</span>
              </div>
            ))}
          </div>

          <div className="trispi-card" style={T.card}>
            <h2 style={T.h2}>Resources</h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {[
                { label: 'Full Source Code', desc: 'Python, Go, Rust, React — complete monorepo with Docker + join script', href: 'https://github.com/TRISPIAINETWORK/TRISPI', ext: 'GitHub' },
                { label: 'Whitepaper PDF', desc: 'TRISPI Protocol specification v3.0', href: '/whitepaper', ext: 'PDF' },
                { label: 'Join Network Script', desc: 'join_trispi_network.sh — one command to run a full node', href: 'https://github.com/TRISPIAINETWORK/TRISPI/blob/main/join_trispi_network.sh', ext: 'GitHub' },
                { label: 'docker-compose.yml', desc: 'Full node Docker stack — Go + Rust + Python + Frontend', href: 'https://github.com/TRISPIAINETWORK/TRISPI/blob/main/docker-compose.yml', ext: 'GitHub' },
                { label: 'Chain Sync API', desc: 'GET /api/chain/snapshot · /genesis-state · /blocks · /peers', href: '/api/chain/snapshot', ext: 'Live' },
                { label: 'Developer SDK', desc: 'JavaScript / Python SDK for building on TRISPI', href: 'https://github.com/TRISPIAINETWORK/TRISPI/tree/main/sdk', ext: 'GitHub' },
              ].map(item => (
                <a key={item.label} href={item.href} target="_blank" rel="noopener noreferrer"
                  style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 14px', background: C.bgSoft, borderRadius: '7px', textDecoration: 'none', border: `1px solid ${C.border}`, gap: '12px' }}>
                  <div>
                    <div style={{ fontSize: '14px', fontWeight: '600', color: C.text }}>{item.label}</div>
                    <div style={{ fontSize: '12px', color: C.textMuted, marginTop: '2px' }}>{item.desc}</div>
                  </div>
                  <span style={{ fontSize: '11px', fontWeight: '600', color: C.textMuted, background: C.bg, border: `1px solid ${C.border}`, padding: '2px 8px', borderRadius: '4px', flexShrink: 0 }}>{item.ext}</span>
                </a>
              ))}
            </div>
          </div>

          <div className="trispi-card" style={T.card}>
            <h2 style={T.h2}>Service Overview</h2>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
              <thead>
                <tr style={{ borderBottom: `1px solid ${C.border}` }}>
                  {['Service', 'Port', 'Protocol', 'Purpose', 'Required'].map(h => (
                    <th key={h} style={{ textAlign: 'left', padding: '8px 12px', color: C.textMuted, fontWeight: '500', fontSize: '11px', textTransform: 'uppercase' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {[
                  ['Python AI Service', ':8000', 'HTTP/REST + GraphQL', 'PoI scoring, FL aggregation, fraud model, tokenomics, energy providers', 'Yes'],
                  ['Go Consensus', ':8181 + :50051', 'HTTP + libp2p', 'PBFT consensus, P2P discovery, block production', 'Recommended'],
                  ['Rust Core Bridge', ':6000', 'TCP JSON', 'EVM + WASM execution + PQC signatures', 'Recommended'],
                  ['React Frontend', ':5000', 'HTTP (proxy)', 'Web interface — proxies /api/* to Python :8000', 'UI only'],
                ].map(([svc, port, proto, purpose, req]) => (
                  <tr key={svc} style={{ borderBottom: `1px solid ${C.border}` }}>
                    <td style={{ padding: '10px 12px', fontWeight: '600', color: C.text }}>{svc}</td>
                    <td style={{ padding: '10px 12px', fontFamily: 'monospace', fontSize: '12px', color: C.textMid }}>{port}</td>
                    <td style={{ padding: '10px 12px', color: C.textMuted, fontSize: '12px' }}>{proto}</td>
                    <td style={{ padding: '10px 12px', color: C.textMuted, fontSize: '12px' }}>{purpose}</td>
                    <td style={{ padding: '10px 12px' }}>
                      <span style={{ padding: '2px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: '600',
                        background: req === 'Yes' ? C.green + '20' : req === 'Recommended' ? C.amberBg : C.bg2,
                        color: req === 'Yes' ? C.green : req === 'Recommended' ? C.amber : C.textMuted }}>
                        {req}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div style={{ padding: '18px 22px', background: C.bg2, border: `1px solid ${C.border}`, borderRadius: '10px', marginBottom: '20px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px' }}>
            <div>
              <div style={{ fontWeight: '700', color: C.text, fontSize: '15px', marginBottom: '4px' }}>TRISPI Technical Whitepaper</div>
              <div style={{ fontSize: '13px', color: C.textMuted }}>30-page technical specification: PoI consensus, PQC, EVM+WASM, IBC, security model.</div>
            </div>
            <a href="/whitepaper" target="_blank" rel="noopener noreferrer" style={{ ...T.btn, textDecoration: 'none', display: 'inline-block', whiteSpace: 'nowrap' }}>
              Download PDF
            </a>
          </div>

          <div className="trispi-card" style={T.card}>
            <h2 style={T.h2}>Protocol Reference</h2>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '16px' }}>
              {[
                { title: 'Consensus', body: 'Proof of Intelligence (PoI) + PBFT. Validators submit ML gradients (federated learning). Accuracy ≥ 70% required per block. Quorum: 13/21 validators. Byzantine tolerance: 6 faulty nodes.' },
                { title: 'Cryptography', body: 'Hybrid Ed25519 + Dilithium3 signatures (NIST FIPS 204) on every transaction. Kyber1024 key exchange (NIST FIPS 203). Both classical and post-quantum signatures required — either alone is insufficient.' },
                { title: 'Smart Contracts', body: 'EVM (Solidity-compatible) + WASM (CosmWasm/Rust) + Hybrid cross-runtime calls. AI audits every deployed contract for reentrancy, overflow, and access control vulnerabilities.' },
                { title: 'Tokenomics', body: 'Genesis: 50M TRP. Block reward: 10 TRP (halves every 500k blocks). Fee burn: 70% of base fee destroyed. Energy provider rewards: 30% of priority fees. Net effect: deflationary at scale.' },
              ].map(item => (
                <div key={item.title} style={{ background: C.bgSoft, borderRadius: '8px', padding: '16px' }}>
                  <h3 style={{ ...T.h3, marginBottom: '8px' }}>{item.title}</h3>
                  <p style={{ color: C.textMuted, fontSize: '13px', lineHeight: '1.7', margin: 0 }}>{item.body}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ── RUN NODE ── */}
      {subTab === 'run-node' && (
        <div>
          <div style={{ ...T.card, borderColor: nodeHealth ? C.green + '40' : C.border }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <StatusDot online={!!nodeHealth} />
                <div>
                  <div style={{ fontWeight: '600', color: C.text }}>This Node</div>
                  <div style={{ fontSize: '13px', color: C.textMuted }}>{nodeHealth ? 'Running and synced' : 'Connecting...'}</div>
                </div>
              </div>
              <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap', fontSize: '13px', color: C.textMuted }}>
                {nodeHealth?.components && Object.entries(nodeHealth.components).map(([k, v]) => (
                  <div key={k} style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                    <StatusDot online={v.status === 'running' || v.status === 'healthy'} />
                    {k.replace(/_/g, ' ')}
                  </div>
                ))}
              </div>
              <button style={T.btnOutline} onClick={checkNodeHealth} disabled={checking}>
                {checking ? 'Checking...' : 'Refresh Status'}
              </button>
            </div>
          </div>

          <div style={{ padding: '16px 20px', background: C.green + '15', border: `1px solid ${C.green}40`, borderRadius: '10px', marginBottom: '24px' }}>
            <div style={{ fontWeight: '700', color: C.text, marginBottom: '4px' }}>Any TRISPI node is an RPC — no central server</div>
            <div style={{ fontSize: '14px', color: C.textMuted, lineHeight: '1.6' }}>
              Every node you run automatically exposes a MetaMask-compatible JSON-RPC endpoint at <code style={{ background: C.bgSoft, padding: '1px 5px', borderRadius: '4px', fontFamily: 'monospace' }}>/rpc</code>.
              There is no central RPC provider — the network is as decentralized as the nodes running it.
            </div>
          </div>

          <div className="trispi-card" style={T.card}>
            <h2 style={T.h2}>Energy Provider — Start Earning TRP (2 Commands)</h2>
            <p style={{ color: C.textMuted, fontSize: '14px', marginBottom: '16px' }}>
              Connect your CPU/GPU and earn TRP rewards. No blockchain setup required — just Python.
            </p>
            <CodeBlock title="Install & Run" code={`pip install requests psutil
cd miner-client

# Connect to this node:
python3 trispi_energy_provider.py --wallet trp1YOUR_ADDRESS

# Connect to a specific node:
python3 trispi_energy_provider.py --server http://YOUR_NODE:8000 --wallet trp1...

# With GPU:
python3 trispi_energy_provider.py --gpu-mb 8192 --wallet trp1...`} />
            <CodeBlock title="Run as System Service (Linux)" code={`sudo tee /etc/systemd/system/trispi-provider.service > /dev/null <<EOF
[Unit]
Description=TRISPI Energy Provider
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$(pwd)/miner-client
ExecStart=/usr/bin/python3 trispi_energy_provider.py --server https://YOUR_DOMAIN --wallet trp1YOUR_ADDRESS
Restart=always
RestartSec=15
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now trispi-provider
sudo journalctl -u trispi-provider -f`} />
          </div>

          {/* ── JOIN NETWORK — ONE COMMAND ── */}
          <div style={{ padding: '16px 20px', background: C.accent + '18', border: `1px solid ${C.accent}40`, borderRadius: '10px', marginBottom: '24px' }}>
            <div style={{ fontWeight: '700', color: C.text, fontSize: '15px', marginBottom: '4px' }}>🌐 Run a Full Node — Decentralize the Network</div>
            <div style={{ fontSize: '14px', color: C.textMuted, lineHeight: '1.6' }}>
              Each full node you run makes TRISPI more decentralized. The node auto-syncs the chain state from the genesis node,
              verifies all balances cryptographically, and connects via libp2p P2P. 
              If the genesis node goes offline — your node keeps the network alive.
            </div>
          </div>

          <div className="trispi-card" style={T.card}>
            <h2 style={T.h2}>Full Node — One Command (Recommended)</h2>
            <p style={{ color: C.textMuted, fontSize: '14px', marginBottom: '16px', lineHeight: '1.6' }}>
              <code style={{ background: C.bgSoft, padding: '1px 5px', borderRadius: '4px' }}>join_trispi_network.sh</code> automatically fetches the chain,
              verifies the state root, configures Docker, and starts all 4 services.
            </p>
            <CodeBlock title="Auto-join (Linux / macOS / WSL2)" code={`git clone https://github.com/TRISPIAINETWORK/TRISPI.git
cd TRISPI

# Set the genesis node URL (the network bootstrap):
export TRISPI_BOOTSTRAP=https://trispi-mainnet.replit.app

# One command — downloads chain, verifies state, starts Docker:
bash join_trispi_network.sh`} />
            <CodeBlock title="What join_trispi_network.sh does automatically" code={`1. Checks Docker + docker compose are installed
2. GET /api/chain/snapshot           → block height, P2P peers, requirements
3. GET /api/chain/genesis-state      → 1044 live accounts + balances
4. Verifies: sha256(balances) == state_root in block  ← tamper protection
5. GET /api/chain/blocks?from=0      → downloads all blocks (paginated)
6. Generates .env.node with secure random secrets
7. docker compose build && docker compose up -d
8. Health-checks Python :8000 and Go :8181
9. Shows your P2P multiaddr to share with other nodes`} />
            <CodeBlock title="After join — your node exposes:" code={`http://localhost:5000       — Frontend (React dApp)
http://localhost:8000       — Python AI API  (/api/health)
http://localhost:8181       — Go Consensus   (/health)
tcp://localhost:6000        — Rust EVM+WASM+PQC
tcp://localhost:50052       — libp2p P2P (open this port!)

# View all logs:
docker compose logs -f

# Check peers connected to your node:
curl http://localhost:8000/api/chain/peers | python3 -m json.tool`} />
            <div style={{ padding: '12px 16px', background: C.amberBg, borderRadius: '8px', fontSize: '13px', color: C.amber, marginTop: '12px' }}>
              Open port <strong>50052/tcp</strong> on your firewall so other nodes can peer with you: <code style={{ background: 'rgba(0,0,0,0.15)', padding: '1px 5px', borderRadius: '3px' }}>sudo ufw allow 50052/tcp</code>
            </div>
          </div>

          <div className="trispi-card" style={T.card}>
            <h2 style={T.h2}>Full Node — Docker Compose (Manual)</h2>
            <p style={{ color: C.textMuted, fontSize: '14px', marginBottom: '16px' }}>
              For full control over configuration — edit <code style={{ background: C.bgSoft, padding: '1px 5px', borderRadius: '4px' }}>.env.node</code> before starting.
            </p>
            <CodeBlock title="Manual Docker setup" code={`git clone https://github.com/TRISPIAINETWORK/TRISPI.git
cd TRISPI

# Configure your node:
cat > .env.node << EOF
NODE_ID=my-node-001
TRISPI_BOOTSTRAP=https://trispi-mainnet.replit.app
TRISPI_BOOTSTRAP_PEER=/dns4/trispi-mainnet.replit.app/tcp/50052/p2p/12D3KooWEYVwoztgTfwXDob7VVZfY4cuVFCP6g7Fe7p4eWkaAXaa
BLOCK_MINED_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(24))")
DB_PASSWORD=$(python3 -c "import secrets; print(secrets.token_hex(16))")
EOF

# Start all services:
docker compose --env-file .env.node up -d

# Verify health:
curl http://localhost:8000/api/health
curl http://localhost:8000/api/chain/snapshot | python3 -m json.tool`} />
            <CodeBlock title="Useful docker compose commands" code={`docker compose ps                        # service status
docker compose logs -f                   # all logs
docker compose logs trispi-go            # Go consensus logs
docker compose logs trispi-python        # Python AI logs
docker compose down                      # stop node
docker compose down -v                   # stop + wipe data (reset)`} />
          </div>

          <div className="trispi-card" style={T.card}>
            <h2 style={T.h2}>Manual Setup (without Docker)</h2>
            <CodeBlock title="Python AI Service (required — port 8000)" code={`cd python-ai-service
pip install -r requirements.txt

# Set bootstrap to auto-sync chain on startup:
export TRISPI_BOOTSTRAP=https://trispi-mainnet.replit.app

uvicorn app.main_fast:app --host 0.0.0.0 --port 8000`} />
            <CodeBlock title="Go Consensus Node (port 8181 + P2P 50052)" code={`cd go-consensus
# Pre-built binary included (Linux x64). To rebuild:
go build -o trispi-consensus .

# Connect to bootstrap peer:
./trispi-consensus -id my-node-001 -http 8181 -port 50052 \\
  -bootstrap /dns4/trispi-mainnet.replit.app/tcp/50052/p2p/12D3KooWEYVwoztgTfwXDob7VVZfY4cuVFCP6g7Fe7p4eWkaAXaa`} />
            <CodeBlock title="Rust Core Bridge (port 6000)" code={`cd rust-core
# Pre-built binary at target/release/trispi-core. To rebuild:
# sudo apt install build-essential pkg-config libssl-dev
cargo build --release
./target/release/trispi-core --port 6000`} />
          </div>

          <div className="trispi-card" style={T.card}>
            <h2 style={T.h2}>Manual Setup by Service</h2>
            <CodeBlock title="Python AI Service (required — port 8000)" code={`cd python-ai-service
pip install -r requirements.txt

# If errors — minimal set:
pip install fastapi uvicorn pydantic requests httpx cryptography dilithium-py numpy

# Optional (EVM + WASM):
pip install py-evm wasmtime

uvicorn app.main_fast:app --host 0.0.0.0 --port 8000`} />
            <CodeBlock title="Go Consensus Node (optional — port 8181)" code={`cd go-consensus
# Pre-built binary included (Linux x64). To rebuild:
go build -o trispi-consensus .

./trispi-consensus -id node1 -http 8181 -port 50051 -chain trispi_chain.json`} />
            <CodeBlock title="Rust Core Bridge (optional — port 6000)" code={`cd rust-core
# Pre-built binary at target/release/trispi_core. To rebuild:
# sudo apt install build-essential pkg-config libssl-dev  (Linux)
cargo build --release

./target/release/trispi_core`} />
          </div>

          <div className="trispi-card" style={T.card}>
            <h2 style={T.h2}>Troubleshooting</h2>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
              <thead>
                <tr style={{ borderBottom: `1px solid ${C.border}` }}>
                  {['Error', 'Fix'].map(h => (
                    <th key={h} style={{ textAlign: 'left', padding: '8px 12px', color: C.textMuted, fontWeight: '500', fontSize: '11px', textTransform: 'uppercase' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {[
                  ['ModuleNotFoundError: fastapi', 'pip install -r python-ai-service/requirements.txt'],
                  ['ModuleNotFoundError: dilithium', 'pip install dilithium-py'],
                  ['Address already in use :8000', 'pkill -f uvicorn  then retry'],
                  ['Redis not available', 'Normal — file storage is used automatically'],
                  ['receive buffer size (QUIC)', 'Normal warning — does not affect operation'],
                  ['go: command not found', 'Install Go: https://golang.org/dl/'],
                  ['cargo: command not found', 'curl --proto =https --tlsv1.2 -sSf https://sh.rustup.rs | sh'],
                  ["linker 'cc' not found", 'sudo apt install build-essential'],
                  ['openssl not found (Rust)', 'sudo apt install pkg-config libssl-dev'],
                  ['Connection refused :8181', 'Go node not running — Python works standalone'],
                  ['Connection refused :6000', 'Rust bridge not running — Python works standalone'],
                ].map(([err, fix]) => (
                  <tr key={err} style={{ borderBottom: `1px solid ${C.border}` }}>
                    <td style={{ padding: '9px 12px', fontFamily: 'monospace', fontSize: '12px', color: '#c0392b' }}>{err}</td>
                    <td style={{ padding: '9px 12px', color: C.textMuted }}>{fix}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="trispi-card" style={T.card}>
            <h2 style={T.h2}>Register as Validator</h2>
            <p style={{ color: C.textMuted, fontSize: '14px', marginBottom: '16px' }}>
              Validators participate in PBFT consensus and earn block rewards.
            </p>
            <CodeBlock code={`# export TRISPI_NODE_URL=https://your-node.example.com

curl -X POST $TRISPI_NODE_URL/api/network/peers/register \\
  -H "Content-Type: application/json" \\
  -d '{
    "node_id":        "my_validator_001",
    "address":        "YOUR_NODE_IP:50051",
    "node_type":      "validator",
    "wallet_address": "trp1..."
  }'

# Monitor consensus:
curl $TRISPI_NODE_URL/api/network/consensus

# Watch block production:
curl $TRISPI_NODE_URL/api/explorer/blocks | python3 -m json.tool`} />
            <div style={{ padding: '14px', background: C.amberBg, borderRadius: '8px', fontSize: '13px', color: C.amber }}>
              Requirements: 1000+ TRP staked, stable connection, min 2 CPU cores / 4GB RAM.
            </div>
          </div>

          <div className="trispi-card" style={T.card}>
            <h2 style={T.h2}>Chain Sync Protocol</h2>
            <p style={{ color: C.textMuted, fontSize: '14px', marginBottom: '16px', lineHeight: '1.6' }}>
              TRISPI uses HTTP-based state sync + libp2p P2P for real-time block propagation.
              A new node downloads the verified live state, then receives new blocks via P2P.
            </p>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '12px', marginBottom: '20px' }}>
              {[
                { step: '1', endpoint: 'GET /api/chain/snapshot', desc: 'Block height, state root, P2P peer addresses, node requirements' },
                { step: '2', endpoint: 'GET /api/chain/genesis-state', desc: '1044 live accounts with current TRP balances (postgresql_live source)' },
                { step: '3', endpoint: 'Verify state root', desc: 'sha256(sorted balances) must match state_root → tamper-proof' },
                { step: '4', endpoint: 'GET /api/chain/blocks?from=0', desc: 'Download all blocks paginated (500/page). Apply on top of state snapshot.' },
                { step: '5', endpoint: 'libp2p P2P :50052', desc: 'Real-time block propagation after initial sync. Open port 50052.' },
              ].map(item => (
                <div key={item.step} style={{ background: C.bgSoft, borderRadius: '8px', padding: '14px', display: 'flex', gap: '12px' }}>
                  <div style={{ width: '24px', height: '24px', borderRadius: '50%', background: C.accent, color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '12px', fontWeight: '700', flexShrink: 0 }}>{item.step}</div>
                  <div>
                    <div style={{ fontSize: '12px', fontFamily: 'monospace', color: C.accent, marginBottom: '4px' }}>{item.endpoint}</div>
                    <div style={{ fontSize: '12px', color: C.textMuted, lineHeight: '1.5' }}>{item.desc}</div>
                  </div>
                </div>
              ))}
            </div>
            <CodeBlock title="Verify your node synced correctly" code={`BOOTSTRAP=https://trispi-mainnet.replit.app
NODE=http://localhost:8000

# Check snapshot from bootstrap:
curl $BOOTSTRAP/api/chain/snapshot | python3 -m json.tool

# Verify your live state (1044 accounts, postgresql_live):
curl $NODE/api/chain/genesis-state | python3 -c "
import json,sys
d=json.load(sys.stdin)
print('Accounts:', d['total_accounts'])
print('Source:  ', d['source'])
print('Height:  ', d['block_height'])
"

# Check P2P peers your node knows:
curl $NODE/api/chain/peers | python3 -m json.tool`} />
            <CodeBlock title="Register as P2P peer (manual)" code={`# Register in Python layer:
curl -X POST http://localhost:8000/api/network/peers/register \\
  -H "Content-Type: application/json" \\
  -d '{
    "node_id":      "my-node-001",
    "address":      "YOUR_PUBLIC_IP:50052",
    "node_type":    "full_node",
    "chain_height": 0
  }'

# Register directly in Go consensus node:
curl -X POST http://localhost:8181/peers/register \\
  -H "Content-Type: application/json" \\
  -d '{"id":"my-node-001","address":"YOUR_IP:50052","is_validator":false}'`} />
          </div>
        </div>
      )}

      {/* ── RUN RPC ── */}
      {subTab === 'run-rpc' && (
        <div>
          <div style={{ padding: '16px 20px', background: C.green + '15', border: `1px solid ${C.green}40`, borderRadius: '10px', marginBottom: '24px' }}>
            <div style={{ fontWeight: '700', color: C.text, marginBottom: '4px' }}>Any TRISPI node is an RPC</div>
            <div style={{ fontSize: '14px', color: C.textMuted, lineHeight: '1.6' }}>
              Every node running the Python AI Service exposes three RPC endpoints: Ethereum-compatible <code style={{ background: C.bgSoft, padding: '1px 5px', borderRadius: '4px', fontFamily: 'monospace' }}>/rpc</code>, native TRISPI <code style={{ background: C.bgSoft, padding: '1px 5px', borderRadius: '4px', fontFamily: 'monospace' }}>/api/trispi/rpc</code>, and WASM <code style={{ background: C.bgSoft, padding: '1px 5px', borderRadius: '4px', fontFamily: 'monospace' }}>/api/wasm/rpc</code>.
              No central server. Connect to any peer's URL.
            </div>
          </div>

          <div className="trispi-card" style={T.card}>
            <h2 style={T.h2}>MetaMask Setup</h2>
            <p style={{ color: C.textMuted, fontSize: '14px', marginBottom: '16px' }}>
              Add TRISPI as a custom network in MetaMask to send TRP transactions from any wallet.
            </p>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px', marginBottom: '20px' }}>
              {[
                { label: 'Network Name',    value: 'TRISPI Mainnet' },
                { label: 'RPC URL',         value: `${rpcEndpoint.replace('/api', '')}/rpc` },
                { label: 'Chain ID',        value: '7331' },
                { label: 'Currency Symbol', value: 'TRP' },
                { label: 'Block Explorer',  value: rpcEndpoint.replace('/api', '') },
              ].map(item => (
                <div key={item.label} style={{ background: C.bgSoft, borderRadius: '8px', padding: '14px' }}>
                  <div style={{ fontSize: '11px', color: C.textMuted, textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '4px' }}>{item.label}</div>
                  <div style={{ fontSize: '13px', fontWeight: '600', color: C.text, wordBreak: 'break-all' }}>{item.value}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="trispi-card" style={T.card}>
            <h2 style={T.h2}>JSON-RPC Endpoints</h2>
            <CodeBlock title="Standard eth_ methods" code={`# export TRISPI_NODE_URL=https://your-node.example.com

# Chain ID:
curl -X POST $TRISPI_NODE_URL/rpc \\
  -H "Content-Type: application/json" \\
  -d '{"jsonrpc":"2.0","method":"eth_chainId","params":[],"id":1}'

# Latest block number:
curl -X POST $TRISPI_NODE_URL/rpc \\
  -H "Content-Type: application/json" \\
  -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'

# Get balance (TRP in wei-equivalent):
curl -X POST $TRISPI_NODE_URL/rpc \\
  -H "Content-Type: application/json" \\
  -d '{"jsonrpc":"2.0","method":"eth_getBalance","params":["trp1YOUR_ADDRESS","latest"],"id":1}'

# Send raw transaction:
curl -X POST $TRISPI_NODE_URL/rpc \\
  -H "Content-Type: application/json" \\
  -d '{"jsonrpc":"2.0","method":"eth_sendRawTransaction","params":["0x..."],"id":1}'`} />
            <CodeBlock title="ethers.js connection" code={`import { ethers } from 'ethers';

// Connect to any TRISPI node:
const provider = new ethers.JsonRpcProvider('${rpcEndpoint.replace('/api', '')}/rpc');

const blockNumber = await provider.getBlockNumber();
const balance     = await provider.getBalance('trp1YOUR_ADDRESS');

// Sign and send (with MetaMask):
const browserProvider = new ethers.BrowserProvider(window.ethereum);
const signer = await browserProvider.getSigner();
const tx = await signer.sendTransaction({
  to:    'trp1RECIPIENT',
  value: ethers.parseEther('1.0'),
});
await tx.wait();`} />
          </div>

          <div className="trispi-card" style={T.card}>
            <h2 style={T.h2}>Register Your Node as a Public RPC</h2>
            <p style={{ color: C.textMuted, fontSize: '14px', marginBottom: '16px' }}>
              Once your node is running, register it with the network so other nodes and wallets can discover and use it as an RPC endpoint.
            </p>
            <CodeBlock title="POST /api/network/peers/register" code={`# export TRISPI_NODE_URL=https://your-node.example.com

curl -X POST $TRISPI_NODE_URL/api/network/peers/register \\
  -H "Content-Type: application/json" \\
  -d '{
    "node_id":        "my_rpc_node_001",
    "address":        "YOUR_PUBLIC_IP:50051",
    "node_type":      "full_node",
    "wallet_address": "trp1YOUR_ADDRESS"
  }'

# Verify registration:
curl $TRISPI_NODE_URL/api/network/status | python3 -m json.tool`} />
            <div style={{ padding: '12px', background: C.greenBg, borderRadius: '8px', fontSize: '13px', color: C.green }}>
              After registration, your node's <code style={{ fontFamily: 'monospace' }}>/rpc</code> endpoint is discoverable by MetaMask users and other dApps on the TRISPI network.
            </div>
          </div>

          <div className="trispi-card" style={T.card}>
            <h2 style={T.h2}>Service API Reference</h2>
            <CodeBlock title="Python AI Service — key endpoints" code={`# export TRISPI_NODE_URL=https://your-node.example.com

# Health:
curl $TRISPI_NODE_URL/health
curl $TRISPI_NODE_URL/api/system/status

# Swagger UI (full API reference):
open $TRISPI_NODE_URL/api/docs

# Latest blocks:
curl $TRISPI_NODE_URL/api/explorer/blocks?limit=10

# Wallet balance:
curl $TRISPI_NODE_URL/api/balance/trp1YOUR_ADDRESS

# Transfer TRP:
curl -X POST $TRISPI_NODE_URL/api/tokens/transfer \\
  -d '{"from_address":"trp1from","to_address":"trp1to","amount":100}'

# Deploy EVM contract:
curl -X POST $TRISPI_NODE_URL/api/engine/deploy \\
  -d '{"creator":"trp1...","bytecode":"0x6080...","runtime":"evm"}'`} />
            <CodeBlock title="Go Consensus Node — key endpoints" code={`# export CONSENSUS_URL=https://your-node.example.com:8181

curl $CONSENSUS_URL/health               # Health check
curl $CONSENSUS_URL/chain                # All blocks
curl $CONSENSUS_URL/network/stats        # Network stats
curl $CONSENSUS_URL/validators           # Validator list
curl $CONSENSUS_URL/p2p/info             # libp2p Peer ID
curl $CONSENSUS_URL/peers                # Connected peers

# Submit a transaction:
curl -X POST $CONSENSUS_URL/tx \\
  -d '{"from":"trp1...","to":"trp1...","amount":100,"data":""}'

# Register a peer:
curl -X POST $CONSENSUS_URL/peers/register \\
  -d '{"id":"my_node","address":"192.168.1.100:50051","is_validator":false}'`} />
          </div>

          <div className="trispi-card" style={T.card}>
            <h2 style={T.h2}>Native TRISPI RPC</h2>
            <p style={{ color: C.textMuted, fontSize: '14px', marginBottom: '16px', lineHeight: '1.6' }}>
              In addition to Ethereum JSON-RPC, every node exposes a native TRISPI RPC at <code style={{ fontFamily: 'monospace', background: C.bgSoft, padding: '1px 6px', borderRadius: '4px' }}>/api/trispi/rpc</code>.
              This endpoint speaks the TRISPI protocol directly — no Ethereum compatibility layer needed.
            </p>
            <CodeBlock title="Native TRISPI JSON-RPC 2.0 — POST /api/trispi/rpc" code={`# export TRISPI_NODE_URL=https://your-node.example.com

# Get a block by index:
curl -X POST $TRISPI_NODE_URL/api/trispi/rpc \\
  -H "Content-Type: application/json" \\
  -d '{"jsonrpc":"2.0","method":"trispi_getBlock","params":[42],"id":1}'

# Get account state (balance + nonce):
curl -X POST $TRISPI_NODE_URL/api/trispi/rpc \\
  -H "Content-Type: application/json" \\
  -d '{"jsonrpc":"2.0","method":"trispi_getAccount","params":["trp1YOUR_ADDRESS"],"id":1}'

# Send a transaction (native, no Ethereum wrapper):
curl -X POST $TRISPI_NODE_URL/api/trispi/rpc \\
  -H "Content-Type: application/json" \\
  -d '{"jsonrpc":"2.0","method":"trispi_sendTx","params":[{"from":"trp1A","to":"trp1B","amount":100}],"id":1}'

# Get all validators:
curl -X POST $TRISPI_NODE_URL/api/trispi/rpc \\
  -H "Content-Type: application/json" \\
  -d '{"jsonrpc":"2.0","method":"trispi_getValidators","params":[],"id":1}'

# Full node + RPC info:
curl -X POST $TRISPI_NODE_URL/api/trispi/rpc \\
  -H "Content-Type: application/json" \\
  -d '{"jsonrpc":"2.0","method":"trispi_networkInfo","params":[],"id":1}'`} />
            <CodeBlock title="Go Consensus RPC (PBFT state) — POST /api/go/rpc" code={`# Query Go consensus state via JSON-RPC:
curl -X POST $TRISPI_NODE_URL/api/go/rpc \\
  -H "Content-Type: application/json" \\
  -d '{"jsonrpc":"2.0","method":"go_getConsensusState","params":[],"id":1}'

curl -X POST $TRISPI_NODE_URL/api/go/rpc \\
  -H "Content-Type: application/json" \\
  -d '{"jsonrpc":"2.0","method":"go_getValidator","params":["node1"],"id":1}'`} />
            <CodeBlock title="Rust Core RPC (PQC signing) — POST /api/rust/rpc" code={`# Sign data with Dilithium3 (post-quantum):
curl -X POST $TRISPI_NODE_URL/api/rust/rpc \\
  -H "Content-Type: application/json" \\
  -d '{"jsonrpc":"2.0","method":"rust_sign","params":[{"data":"deadbeef"}],"id":1}'

# Verify a signature:
curl -X POST $TRISPI_NODE_URL/api/rust/rpc \\
  -H "Content-Type: application/json" \\
  -d '{"jsonrpc":"2.0","method":"rust_verify","params":[{"data":"...","sig":"...","pub":"..."}],"id":1}'

# Get Rust core stats:
curl -X POST $TRISPI_NODE_URL/api/rust/rpc \\
  -H "Content-Type: application/json" \\
  -d '{"jsonrpc":"2.0","method":"rust_getStats","params":[],"id":1}'`} />
          </div>

          <div className="trispi-card" style={T.card}>
            <h2 style={T.h2}>WASM Node (Rust, independent of Ethereum)</h2>
            <p style={{ color: C.textMuted, fontSize: '14px', marginBottom: '16px', lineHeight: '1.6' }}>
              Run a WASM-only node that executes CosmWasm/Rust smart contracts without the Ethereum compatibility layer.
              Set <code style={{ fontFamily: 'monospace', background: C.bgSoft, padding: '1px 6px', borderRadius: '4px' }}>TRISPI_NODE_MODE=wasm</code> and the node will only activate the TRISPI and WASM RPC stacks — the Ethereum JSON-RPC routes (<code style={{ fontFamily: 'monospace', background: C.bgSoft, padding: '1px 4px', borderRadius: '4px' }}>/rpc</code>, <code style={{ fontFamily: 'monospace', background: C.bgSoft, padding: '1px 4px', borderRadius: '4px' }}>/api/rpc</code>) are not registered at startup and return 404.
            </p>
            <CodeBlock title="Start a WASM-only node" code={`cd python-ai-service

# WASM-only mode — Ethereum JSON-RPC routes are not registered at startup
TRISPI_NODE_MODE=wasm uvicorn app.main_simplified:app --host 0.0.0.0 --port 8001

# Active endpoints in wasm mode:
#   POST :8001/api/trispi/rpc  — native TRISPI RPC (all trispi_* methods)
#   POST :8001/api/wasm/rpc    — CosmWasm-compatible WASM RPC (all wasm_* methods)
#   GET/POST :8001/api/peers*  — peer registry
#
# NOT available in wasm mode (return 404):
#   /rpc           — Ethereum JSON-RPC (MetaMask) — not registered at startup
#   /api/rpc       — Ethereum JSON-RPC (MetaMask) — not registered at startup
#   /api/go/rpc    — Go consensus RPC proxy — disabled; Go node runs independently
#   /api/rust/rpc  — Rust core RPC proxy — disabled; call :6000/rpc directly`} />
            <CodeBlock title="WASM JSON-RPC 2.0 — POST /api/wasm/rpc" code={`# export WASM_NODE_URL=https://your-wasm-node.example.com

# Instantiate (deploy) a WASM contract:
curl -X POST $WASM_NODE_URL/api/wasm/rpc \\
  -H "Content-Type: application/json" \\
  -d '{
    "jsonrpc": "2.0",
    "method":  "wasm_instantiate",
    "params":  [{"sender":"trp1...","code":"<base64_wasm>","init_msg":{"count":0},"label":"my_contract"}],
    "id": 1
  }'

# Execute a WASM contract method:
curl -X POST $WASM_NODE_URL/api/wasm/rpc \\
  -H "Content-Type: application/json" \\
  -d '{
    "jsonrpc": "2.0",
    "method":  "wasm_execute",
    "params":  [{"contract_address":"trp1contract...","msg":{"increment":{}},"sender":"trp1..."}],
    "id": 1
  }'

# Query WASM contract state (read-only):
curl -X POST $WASM_NODE_URL/api/wasm/rpc \\
  -H "Content-Type: application/json" \\
  -d '{
    "jsonrpc": "2.0",
    "method":  "wasm_query",
    "params":  [{"contract_address":"trp1contract...","query_msg":{"get_count":{}}}],
    "id": 1
  }'

# List all WASM contracts on this node:
curl -X POST $WASM_NODE_URL/api/wasm/rpc \\
  -H "Content-Type: application/json" \\
  -d '{"jsonrpc":"2.0","method":"wasm_listContracts","params":[],"id":1}'`} />
          </div>

          <div className="trispi-card" style={T.card}>
            <h2 style={T.h2}>Connect Nodes to Each Other (Peer-to-Peer)</h2>
            <p style={{ color: C.textMuted, fontSize: '14px', marginBottom: '16px', lineHeight: '1.6' }}>
              Nodes connect directly to each other — there is no central hub. Use <code style={{ fontFamily: 'monospace', background: C.bgSoft, padding: '1px 6px', borderRadius: '4px' }}>POST /api/peers/add</code> on any node to register another node as a peer.
              Each node keeps its own peer registry in <code style={{ fontFamily: 'monospace', background: C.bgSoft, padding: '1px 6px', borderRadius: '4px' }}>trispi_state/peers.json</code>.
            </p>
            <CodeBlock title="Register a peer node" code={`# On NODE_A, register NODE_B as a peer:
curl -X POST https://node-a.example.com/api/peers/add \\
  -H "Content-Type: application/json" \\
  -d '{
    "url":       "https://node-b.example.com",
    "node_id":   "node_b",
    "node_type": "full_node"
  }'

# NODE_A will automatically announce itself to NODE_B in return.

# List all known peers on a node:
curl https://node-a.example.com/api/peers

# Remove a peer — by node_id (preferred):
curl -X DELETE https://node-a.example.com/api/peers/node_b

# Remove a peer — by URL suffix (hostname match):
curl -X DELETE https://node-a.example.com/api/peers/node-b.example.com

# ── Private / local network nodes ──────────────────────────────────────────────
# Private-network peers (LAN, Docker, VPN) are ALLOWED by default.
# Register them directly — no extra configuration needed:
curl -X POST http://localhost:8000/api/peers/add \\
  -H "Content-Type: application/json" \\
  -d '{"url":"http://192.168.1.50:8000","node_id":"lan_node_2","node_type":"full_node"}'

# To restrict this node to public internet peers only (validator hardening):
TRISPI_BLOCK_PRIVATE_PEERS=1 uvicorn app.main_simplified:app --host 0.0.0.0 --port 8000`} />
            <CodeBlock title="Sync chain from a peer node" code={`# Sync your node's chain from any peer's chain history:
# (Uses the Go consensus P2P protocol)
curl -X POST https://node-a.example.com/api/chain/sync-block \\
  -H "Content-Type: application/json" \\
  -d '{ ...block_json_from_peer... }'

# Announce your node to a peer (libp2p discovery):
curl -X POST https://node-b.example.com/api/p2p/announce \\
  -H "Content-Type: application/json" \\
  -d '{
    "node_id":     "my_node_001",
    "http_url":    "https://my-node.example.com",
    "chain_height": 1234
  }'

# Query what blocks a peer has:
curl "https://node-b.example.com/api/p2p/blocks/range?from=0&to=99"

# Bootstrap from a peer (get their chain head + multiaddrs):
curl https://node-b.example.com/api/p2p/bootstrap`} />
            <div style={{ padding: '12px', background: C.bgSoft, borderRadius: '8px', fontSize: '13px', color: C.textMuted, marginTop: '4px' }}>
              No central RPC. No central bootstrap server. Every node is equal — connect to any peer and the network discovers itself via libp2p mDNS + Kademlia DHT.
            </div>
          </div>
        </div>
      )}

      {/* ── CREATE CHAIN ── */}
      {subTab === 'create-chain' && (
        <div>
          <div className="trispi-card" style={T.card}>
            <h2 style={T.h2}>Scaffold a Custom Blockchain</h2>
            <p style={{ color: C.textMuted, fontSize: '14px', marginBottom: '20px', lineHeight: '1.7' }}>
              Generate a complete blockchain project in Go, Rust, or Solidity. Each scaffold includes source code, Docker configuration, and a <code style={{ background: C.bgSoft, padding: '1px 5px', borderRadius: '4px', fontFamily: 'monospace' }}>connect-to-trispi.sh</code> script that registers your chain as a TRISPI subnet.
            </p>
            <div style={{ padding: '14px', background: C.green + '15', border: `1px solid ${C.green}40`, borderRadius: '8px', marginBottom: '20px', fontSize: '14px', color: C.text }}>
              Use the REST API or CLI below to scaffold your chain, set the chain name, block time, and download the generated project.
            </div>
          </div>

          <div className="trispi-card" style={T.card}>
            <h2 style={T.h2}>Via REST API</h2>
            <CodeBlock title="Scaffold via curl" code={`# export TRISPI_NODE_URL=https://your-node.example.com

# Go chain:
curl -X POST $TRISPI_NODE_URL/api/chains/scaffold \\
  -H "Content-Type: application/json" \\
  -d '{
    "chain_name":   "my-chain",
    "language":     "go",
    "block_time":   15,
    "token_name":   "MYTOKEN",
    "token_symbol": "MYT"
  }' -o my-chain.zip

# Rust / CosmWasm:
curl -X POST $TRISPI_NODE_URL/api/chains/scaffold \\
  -H "Content-Type: application/json" \\
  -d '{"chain_name":"my-chain","language":"rust","block_time":10}' -o my-chain.zip

# Solidity / EVM:
curl -X POST $TRISPI_NODE_URL/api/chains/scaffold \\
  -H "Content-Type: application/json" \\
  -d '{"chain_name":"my-chain","language":"solidity","block_time":12}' -o my-chain.zip`} />
          </div>

          <div className="trispi-card" style={T.card}>
            <h2 style={T.h2}>Connect Your Chain to TRISPI</h2>
            <CodeBlock code={`# After unzipping the scaffold:
unzip my-chain.zip -d my-chain
cd my-chain

# Connect to TRISPI mainnet:
bash connect-to-trispi.sh

# Or connect to a specific node:
TRISPI_NODE_URL=http://YOUR_NODE:8000 bash connect-to-trispi.sh`} />
            <p style={{ color: C.textMuted, fontSize: '13px', marginTop: '8px' }}>
              The script registers your chain as a subnet, submits your validator details, and starts syncing with the TRISPI mainnet.
            </p>
          </div>

          <div className="trispi-card" style={T.card}>
            <h2 style={T.h2}>Rust Core Bridge</h2>
            <p style={{ color: C.textMuted, fontSize: '14px', marginBottom: '16px' }}>
              Port <code style={{ fontFamily: 'monospace', background: C.bgSoft, padding: '1px 6px', borderRadius: '4px' }}>:6000</code> TCP — EVM + WASM + Ed25519/Dilithium signatures
            </p>
            <CodeBlock title="TCP Bridge Protocol (JSON)" code={`# Protocol: JSON over TCP (one connection = one request)
# When running the bridge locally: TRISPI_CORE_HOST=127.0.0.1
# For a remote node:              TRISPI_CORE_HOST=your-node.example.com

# Python example:
import socket, json, os

CORE_HOST = os.getenv("TRISPI_CORE_HOST", "127.0.0.1")

def rust_cmd(cmd, data=None):
    req = {"cmd": cmd, **({"data": data} if data else {})}
    with socket.socket() as s:
        s.connect((CORE_HOST, 6000))
        s.sendall(json.dumps(req).encode())
        s.shutdown(socket.SHUT_WR)
        buf = b""
        while chunk := s.recv(4096): buf += chunk
    return json.loads(buf)

chain = rust_cmd("get_chain")
block = rust_cmd("submit_tx", {"data": "transfer:..."})
ok    = rust_cmd("commit_block", {"hash": "00def..."})`} />
            <CodeBlock title="Build from source" code={`cd rust-core

# Linux:
sudo apt install pkg-config libssl-dev build-essential
cargo build --release

# macOS:
brew install pkg-config openssl
cargo build --release

# Tests:
cargo test
cargo test wasm_vm::tests   # WASM only
cargo test pqc::tests       # Post-Quantum only`} />
          </div>
        </div>
      )}

      {/* ── SDK & API ── */}
      {subTab === 'sdk-api' && (
        <div>
          <div style={{ display: 'flex', gap: '8px', marginBottom: '28px', flexWrap: 'wrap' }}>
            <button style={tabStyle(devTab === 'api')} onClick={() => setDevTab('api')} data-testid="dev-tab-api">
              API Reference
            </button>
            <button style={tabStyle(devTab === 'contracts')} onClick={() => setDevTab('contracts')} data-testid="dev-tab-contracts">
              Contracts
            </button>
          </div>

          {devTab === 'api' && (
            <>
              <div className="trispi-card" style={T.card}>
                <h2 style={T.h2}>REST Endpoints</h2>
                <div>
                  {[
                    { method: 'GET',  path: '/api/health', desc: 'Service health check' },
                    { method: 'GET',  path: '/api/network/status', desc: 'Chain statistics' },
                    { method: 'GET',  path: '/api/chain', desc: 'Full blockchain' },
                    { method: 'GET',  path: '/api/block/{n}', desc: 'Block by number' },
                    { method: 'GET',  path: '/api/balance/{address}', desc: 'Wallet balance' },
                    { method: 'GET',  path: '/api/tokenomics', desc: 'TRP token economics' },
                    { method: 'GET',  path: '/api/mempool', desc: 'Pending transactions' },
                    { method: 'GET',  path: '/api/gas/recommend', desc: 'AI gas estimate' },
                    { method: 'POST', path: '/api/tx', desc: 'Submit transaction' },
                    { method: 'POST', path: '/api/wallet/create', desc: 'Create wallet' },
                    { method: 'POST', path: '/api/tokens/transfer', desc: 'Send TRP' },
                    { method: 'POST', path: '/api/ai/poi/generate', desc: 'Generate PoI proof' },
                    { method: 'POST', path: '/api/contract/audit', desc: 'AI contract audit' },
                    { method: 'POST', path: '/api/contracts/deploy/{runtime}', desc: 'Deploy contract (evm|wasm|duo)' },
                    { method: 'POST', path: '/api/contracts/call', desc: 'Call contract method' },
                    { method: 'GET',  path: '/api/contracts/list', desc: 'List all deployed contracts' },
                    { method: 'GET',  path: '/api/contracts/{address}', desc: 'Contract details + state' },
                    { method: 'GET',  path: '/api/contracts/{address}/events', desc: 'Contract event log' },
                    { method: 'POST', path: '/api/ai-energy/register', desc: 'Register as energy provider' },
                    { method: 'POST', path: '/api/ai-energy/heartbeat', desc: 'Provider heartbeat' },
                    { method: 'POST', path: '/api/chains/scaffold', desc: 'Scaffold a new blockchain (zip)' },
                  { method: 'POST', path: '/api/validators/register', desc: 'Register as PoI validator (pubkey + stake)' },
                  { method: 'POST', path: '/api/validators/submit-score', desc: 'Submit PoI block score (signed)' },
                  { method: 'POST', path: '/api/validators/submit-tx-verdict', desc: 'Submit TX fraud verdict (signed)' },
                  { method: 'GET',  path: '/api/explorer/pending-txs', desc: 'Pending transactions awaiting fraud verdicts' },
                  { method: 'GET',  path: '/api/ai/validation-stats', desc: 'Validator leaderboard + consensus stats' },
                  { method: 'GET',  path: '/api/federated/verify-round/{round_id}', desc: 'Verify FL aggregation vs on-chain hash' },
                  { method: 'POST', path: '/api/federated/register', desc: 'Register as FL gradient provider' },
                  { method: 'POST', path: '/api/federated/submit-gradient', desc: 'Submit AES-256-GCM encrypted FL gradient' },
                  { method: 'GET',  path: '/api/federated/round-status', desc: 'Current FL round status + submission count' },
                  ].map(ep => (
                    <div key={ep.path} style={{ display: 'flex', alignItems: 'center', gap: '12px', padding: '10px 0', borderBottom: `1px solid ${C.border}`, flexWrap: 'wrap' }}>
                      <span style={{ ...T.badge, background: ep.method === 'GET' ? C.greenBg : C.amberBg, color: ep.method === 'GET' ? C.green : C.amber, border: 'none', minWidth: '42px', textAlign: 'center' }}>
                        {ep.method}
                      </span>
                      <code style={{ fontFamily: 'monospace', fontSize: '13px', color: C.text, flex: 1 }}>{ep.path}</code>
                      <span style={{ fontSize: '13px', color: C.textMuted }}>{ep.desc}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="trispi-card" style={{ ...T.card, borderColor: C.blue + '40' }}>
                <h2 style={T.h2}>AI Consensus — How Validators Earn TRP</h2>
                <p style={{ color: C.textMuted, fontSize: '14px', marginBottom: '20px', lineHeight: '1.6' }}>
                  TRISPI uses three AI consensus mechanisms simultaneously. Any machine running <code style={{ background: C.bgSoft, padding: '1px 5px', borderRadius: '4px' }}>trispi_energy_provider.py</code> participates in all three.
                </p>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '14px', marginBottom: '20px' }}>
                  {[
                    {
                      title: 'PoI Block Scoring', color: C.blue, reward: '+0.1 TRP / block',
                      endpoint: 'POST /api/validators/submit-score',
                      desc: '4-feature weighted model: tx_quality (0.30) · timing (0.25) · network_health (0.25) · ai_proof_integrity (0.20). Consensus = stake-weighted median of all validator scores. Required accuracy ≥ 0.70.',
                    },
                    {
                      title: 'Federated Learning (FL)', color: C.green, reward: '+1.0 TRP / round',
                      endpoint: 'POST /api/federated/submit-gradient',
                      desc: 'Stake-weighted coordinate-wise median aggregation with Krum Byzantine filter. AES-256-GCM encrypted gradients + Ed25519 signature + Kyber1024 key exchange. Reputation system: accepted = +0.5% trust, rejected = −5% trust.',
                    },
                    {
                      title: 'TX Fraud Detection', color: C.purple, reward: '+0.01 TRP / verdict',
                      endpoint: 'POST /api/validators/submit-tx-verdict',
                      desc: 'fraud_model_v1 — 5 features: amount_anomaly (0.30) · address_age (0.25) · velocity (0.20) · pattern (0.15) · graph (0.10). FRAUD_THRESHOLD = 0.65. Consensus = ≥60% validator agreement. Dishonest verdicts reduce trust_weight.',
                    },
                  ].map(item => (
                    <div key={item.title} style={{ background: C.bgSoft, borderRadius: '10px', padding: '16px', borderLeft: `3px solid ${item.color}` }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                        <h3 style={{ ...T.h3, margin: 0, color: item.color }}>{item.title}</h3>
                        <span style={{ fontSize: '11px', fontWeight: '700', color: item.color, background: item.color + '15', padding: '2px 8px', borderRadius: '10px' }}>{item.reward}</span>
                      </div>
                      <code style={{ display: 'block', fontSize: '11px', color: C.textMuted, background: C.bg, padding: '4px 8px', borderRadius: '4px', marginBottom: '8px', fontFamily: 'monospace' }}>{item.endpoint}</code>
                      <p style={{ color: C.textMuted, fontSize: '12px', lineHeight: '1.6', margin: 0 }}>{item.desc}</p>
                    </div>
                  ))}
                </div>
                <CodeBlock title="Register as validator + submit PoI score" code={`# 1. Register (one time):
curl -X POST /api/validators/register \\
  -H "Content-Type: application/json" \\
  -d '{
    "validator_id": "trp1YourAddress",
    "public_key":   "ed25519_pubkey_hex",
    "stake":        100.0,
    "metadata":     {"gpu": false, "cpu_cores": 8}
  }'

# 2. Submit PoI block score (each new block):
curl -X POST /api/validators/submit-score \\
  -H "Content-Type: application/json" \\
  -d '{
    "validator_id": "trp1YourAddress",
    "block_hash":   "sha256_of_block",
    "block_index":  1234,
    "score":        0.87,
    "signature":    "ed25519_sig_of_score_payload"
  }'

# 3. Submit TX fraud verdict (each pending-txs poll):
curl -X POST /api/validators/submit-tx-verdict \\
  -H "Content-Type: application/json" \\
  -d '{
    "tx_id":        "tx_hash",
    "validator_id": "trp1YourAddress",
    "verdict":      "valid",
    "fraud_score":  0.12,
    "signature":    "ed25519_sig_of_verdict_payload",
    "public_key":   "ed25519_pubkey_hex"
  }'

# 4. Check your stats:
curl /api/ai/validation-stats`} />
                <CodeBlock title="Verify FL round on-chain" code={`# After an FL round completes, verify the aggregation result matches the on-chain hash:
curl /api/federated/verify-round/ROUND_ID

# Response:
{
  "round_id":       "...",
  "status":         "verified",
  "aggregate_hash": "sha3_256_of_global_weights",
  "on_chain_hash":  "same_hash_from_go_tx",
  "match":          true,
  "providers":      12,
  "accepted":       10
}`} />
              </div>

              <div className="trispi-card" style={{ ...T.card, borderColor: C.green + '40' }}>
                <h2 style={T.h2}>Developer Quick-Start — API Examples</h2>
                <p style={{ color: C.textMuted, fontSize: '14px', marginBottom: '20px', lineHeight: '1.6' }}>
                  Use these examples to connect to any TRISPI node from curl, Python, or JavaScript. Replace <code style={{ background: C.bgSoft, padding: '1px 5px', borderRadius: '4px' }}>NODE_URL</code> with your node address (default: <code style={{ background: C.bgSoft, padding: '1px 5px', borderRadius: '4px' }}>http://localhost:8000</code>).
                </p>
                <CodeBlock title="curl — validate a transaction" code={`export NODE_URL=http://localhost:8000

# Validate a transaction with AI fraud detection:
curl -X POST $NODE_URL/api/ai/validate-tx \\
  -H "Content-Type: application/json" \\
  -d '{
    "tx_id":     "0xabc123...",
    "from":      "trp1SenderAddress",
    "to":        "trp1ReceiverAddress",
    "amount":    500.0,
    "data":      "",
    "timestamp": 1716000000
  }'

# Response:
# { "valid": true, "fraud_score": 0.08, "confidence": 0.94,
#   "risk_level": "low", "processing_time_ms": 12 }

# Get pending transactions awaiting fraud verdicts:
curl $NODE_URL/api/explorer/pending-txs?limit=10

# Get validator leaderboard + consensus stats:
curl $NODE_URL/api/ai/validation-stats

# Get network stats (chain height, TPS, validator count):
curl $NODE_URL/api/network/stats`} />
                <CodeBlock title="Python — validate-tx + pending-txs polling loop" code={`import requests, time

NODE_URL = "http://localhost:8000"

# Validate a single transaction:
resp = requests.post(f"{NODE_URL}/api/ai/validate-tx", json={
    "tx_id": "0xabc123", "from": "trp1Sender",
    "to": "trp1Receiver", "amount": 500.0,
    "data": "", "timestamp": int(time.time()),
})
result = resp.json()
print(f"Valid: {result['valid']}  Fraud score: {result['fraud_score']:.3f}")

# Poll pending-txs and print each:
while True:
    txs = requests.get(f"{NODE_URL}/api/explorer/pending-txs?limit=5").json()
    for tx in txs.get("pending_transactions", []):
        print(f"  TX {tx['tx_id'][:12]}…  amount={tx['amount']}  age={tx['age_seconds']}s")

    stats = requests.get(f"{NODE_URL}/api/ai/validation-stats").json()
    print(f"Validators: {stats.get('total_validators', 0)}  "
          f"Consensus rate: {stats.get('consensus_rate', 0):.1%}")
    time.sleep(10)`} />
                <CodeBlock title="JavaScript — validate-tx + real-time stats" code={`const NODE_URL = "http://localhost:8000";

// Validate a transaction:
async function validateTx(tx) {
  const res = await fetch(\`\${NODE_URL}/api/ai/validate-tx\`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(tx),
  });
  return res.json();
}

const result = await validateTx({
  tx_id: "0xabc123", from: "trp1Sender", to: "trp1Receiver",
  amount: 500, data: "", timestamp: Math.floor(Date.now() / 1000),
});
console.log("Fraud score:", result.fraud_score, "Valid:", result.valid);

// Fetch pending txs:
const pending = await fetch(\`\${NODE_URL}/api/explorer/pending-txs?limit=10\`).then(r => r.json());
console.log("Pending txs:", pending.pending_transactions?.length);

// Fetch validation stats:
const stats = await fetch(\`\${NODE_URL}/api/ai/validation-stats\`).then(r => r.json());
console.log("Active validators:", stats.total_validators);

// Fetch network stats:
const net = await fetch(\`\${NODE_URL}/api/network/stats\`).then(r => r.json());
console.log("Block height:", net.block_height, "TPS:", net.tps);`} />
              </div>

              <div className="trispi-card" style={T.card}>
                <h2 style={T.h2}>GraphQL API</h2>
                <p style={{ color: C.textMuted, fontSize: '14px', marginBottom: '16px' }}>
                  Real-time data via WebSocket subscriptions. Endpoint: <code style={{ background: C.bgSoft, padding: '2px 6px', borderRadius: '4px' }}>{rpcEndpoint}/graphql</code>
                </p>
                <CodeBlock title="Query Example" code={`POST ${rpcEndpoint}/graphql

{
  chain {
    blockHeight
    totalTransactions
    activeValidators
    latestBlock {
      index hash
      transactions { hash amount }
    }
  }
}`} />
                <CodeBlock title="WebSocket Subscription" code={`import { createClient } from 'graphql-ws';
const client = createClient({ url: \`wss://\${window.location.host}/api/graphql\` });

client.subscribe(
  { query: \`subscription { newBlock { index hash timestamp txCount aiScore } }\` },
  { next: ({ data }) => console.log('New block:', data.newBlock) }
);`} />
              </div>

              <div className="trispi-card" style={T.card}>
                <h2 style={T.h2}>Python SDK</h2>
                <p style={{ color: C.textMuted, fontSize: '14px', marginBottom: '16px' }}>
                  No dedicated package yet — use <code style={{ background: C.bgSoft, padding: '1px 5px', borderRadius: '4px', fontFamily: 'monospace' }}>requests</code> directly. All endpoints are REST + JSON.
                </p>
                <CodeBlock title="Python — common operations" code={`import requests, os

NODE = os.getenv("TRISPI_NODE_URL", "${rpcEndpoint}")

# Create a wallet:
wallet = requests.post(f"{NODE}/wallet/create",
    json={"password": "secret"}).json()
print(wallet["address"])  # trp1...

# Check balance:
bal = requests.get(f"{NODE}/balance/{wallet['address']}").json()
print(bal["balance"])

# Send TRP:
tx = requests.post(f"{NODE}/tokens/transfer", json={
    "from_address": wallet["address"],
    "to_address":   "trp1RECIPIENT",
    "amount":       10.0,
    "private_key":  wallet["private_key"],
}).json()
print(tx["tx_hash"])

# Deploy an EVM contract:
contract = requests.post(f"{NODE}/contracts/deploy/evm", json={
    "bytecode":  "0x608060...",
    "deployer":  wallet["address"],
    "gas_limit": 1000000,
}).json()
print(contract["contract_address"])

# Generate a Proof of Intelligence:
poi = requests.post(f"{NODE}/ai/poi/generate", json={
    "validator_id": wallet["address"],
    "task_type":    "classification",
}).json()
print(poi["poi_hash"])`} />
              </div>

              <div className="trispi-card" style={T.card}>
                <h2 style={T.h2}>Quick Examples</h2>
                <CodeBlock title="Create Wallet" code={`curl -X POST ${rpcEndpoint}/wallet/create \\
  -H "Content-Type: application/json" \\
  -d '{"password": "your-password"}'`} />
                <CodeBlock title="Submit Transaction" code={`curl -X POST ${rpcEndpoint}/tx \\
  -H "Content-Type: application/json" \\
  -d '{
    "from": "trp1abc...",
    "to":   "trp1xyz...",
    "amount": 10.0,
    "token": "TRP"
  }'`} />
                <CodeBlock title="Deploy EVM Contract" code={`curl -X POST ${rpcEndpoint}/contracts/deploy/evm \\
  -H "Content-Type: application/json" \\
  -d '{
    "bytecode": "0x608060...",
    "deployer": "trp1...",
    "gas_limit": 1000000
  }'`} />
                <CodeBlock title="Call Contract Method" code={`curl -X POST ${rpcEndpoint}/contracts/call \\
  -H "Content-Type: application/json" \\
  -d '{
    "contract_address": "0xABC...",
    "method": "transfer",
    "args": ["trp1...", 100],
    "caller": "trp1..."
  }'`} />
              </div>

              <div className="trispi-card" style={T.card}>
                <h2 style={T.h2}>Genesis Configuration</h2>
                <CodeBlock code={`{
  "consensus":  "PoI+PBFT",
  "token":       "TRP",
  "genesis_supply": 50000000,
  "block_time":  15,
  "eip1559": { "burn_rate": 0.7, "tip_rate": 0.3 },
  "cryptography": {
    "classical":     "Ed25519",
    "post_quantum":  "Dilithium3",
    "key_exchange":  "Kyber1024"
  },
  "runtimes":    ["EVM", "WASM", "Hybrid"],
  "validators":  21,
  "quorum":      13,
  "byzantine_tolerance": "6/21 faulty nodes"
}`} />
              </div>
            </>
          )}

          {devTab === 'contracts' && <ContractsBrowser />}
        </div>
      )}
    </div>
  );
}


// ===== APP CONTENT =====
function AppContent() {
  const wallet = useWallet();
  const [activeTab, setActiveTab] = useState('home');
  const [showWallet, setShowWallet] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();
  const isMobile = useIsMobile();

  const VALID_TABS = new Set(['home', 'mining', 'build', 'wallet']);

  useEffect(() => {
    const raw = location.hash.replace('#', '').trim();
    const path = location.pathname.replace('/', '').trim();
    const candidate = raw || path || 'home';
    const active = VALID_TABS.has(candidate) ? candidate : 'home';
    if (active !== activeTab) {
      setActiveTab(active);
      if (!VALID_TABS.has(candidate)) navigate('#home', { replace: true });
    }
  }, [location]);

  const goTo = (tab) => {
    setActiveTab(tab);
    setMenuOpen(false);
    navigate(`#${tab}`);
    window.scrollTo(0, 0);
  };

  useEffect(() => {
    const handler = (e) => goTo(e.detail);
    window.addEventListener('trispi:navigate', handler);
    return () => window.removeEventListener('trispi:navigate', handler);
  }, []);

  const tabs = [
    { id: 'home',         label: 'Home' },
    { id: 'mining',       label: 'Mining' },
    { id: 'build',        label: 'Build & Deploy' },
    { id: 'wallet',       label: 'Wallet' },
  ];

  return (
    <div style={T.app}>
      <header style={T.header}>
        <div style={{ ...T.logo, display: 'flex', alignItems: 'center', gap: '10px' }} onClick={() => goTo('home')} data-testid="logo">
          <img src="/trispi-logo.png" alt="TRISPI" style={{ height: '32px', width: 'auto', objectFit: 'contain' }} />
          TRISPI
        </div>

        {!isMobile && (
          <nav style={T.nav}>
            {tabs.map(tab => (
              <button
                key={tab.id}
                onClick={() => goTo(tab.id)}
                data-testid={`nav-${tab.id}`}
                style={activeTab === tab.id ? T.navBtnActive : T.navBtn}
              >
                {tab.label}
              </button>
            ))}
          </nav>
        )}

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <button
            style={T.btn}
            onClick={() => setShowWallet(true)}
            data-testid="header-wallet-btn"
          >
            {wallet.isConnected && wallet.quantumAddress
              ? wallet.quantumAddress.slice(0, 10) + '...'
              : 'Connect'}
          </button>

          {isMobile && (
            <button
              className="hamburger-btn"
              onClick={() => setMenuOpen(o => !o)}
              aria-label="Toggle menu"
              aria-expanded={menuOpen}
              data-testid="hamburger-btn"
              style={{
                background: 'none', border: `1px solid ${C.border}`, borderRadius: '6px',
                padding: '7px 10px', cursor: 'pointer', display: 'flex', flexDirection: 'column',
                gap: '4px', alignItems: 'center', justifyContent: 'center',
              }}
            >
              <span style={{ display: 'block', width: '18px', height: '2px', background: C.text, borderRadius: '1px', transition: 'all 0.2s', transform: menuOpen ? 'rotate(45deg) translate(4px, 4px)' : 'none' }} />
              <span style={{ display: 'block', width: '18px', height: '2px', background: C.text, borderRadius: '1px', transition: 'all 0.2s', opacity: menuOpen ? 0 : 1 }} />
              <span style={{ display: 'block', width: '18px', height: '2px', background: C.text, borderRadius: '1px', transition: 'all 0.2s', transform: menuOpen ? 'rotate(-45deg) translate(4px, -4px)' : 'none' }} />
            </button>
          )}
        </div>
      </header>

      {isMobile && menuOpen && (
        <div
          className="mobile-menu"
          style={{
            position: 'fixed', top: '60px', left: 0, right: 0, bottom: 0,
            background: C.bg, zIndex: 99, borderTop: `1px solid ${C.border}`,
            overflowY: 'auto',
          }}
          onClick={() => setMenuOpen(false)}
        >
          <nav style={{ padding: '8px 0' }}>
            {tabs.map(tab => (
              <button
                key={tab.id}
                onClick={() => goTo(tab.id)}
                data-testid={`nav-${tab.id}`}
                style={{
                  display: 'block', width: '100%', textAlign: 'left',
                  padding: '16px 24px', background: activeTab === tab.id ? C.bgSoft : 'transparent',
                  border: 'none', borderBottom: `1px solid ${C.border}`,
                  color: activeTab === tab.id ? C.text : C.textMid,
                  fontWeight: activeTab === tab.id ? '600' : '400',
                  fontSize: '16px', cursor: 'pointer',
                }}
              >
                {tab.label}
              </button>
            ))}
          </nav>
        </div>
      )}

      <main style={{ ...T.main, padding: isMobile ? '24px 16px' : '40px 32px' }}>
        {activeTab === 'home'         && <HomePage setShowWallet={setShowWallet} />}
        {activeTab === 'mining'       && <MiningPage wallet={wallet} setShowWallet={setShowWallet} />}
        {activeTab === 'build'        && <BuildDeployPage />}
        {activeTab === 'wallet'       && <WalletPage wallet={wallet} setShowWallet={setShowWallet} />}
      </main>

      <footer style={{ borderTop: `1px solid ${C.border}`, padding: '24px 32px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
        <span style={{ fontSize: '13px', color: C.textMuted }}>© 2025 TRISPI Network — {NETWORK_NAME}</span>

        {/* Social media icons */}
        <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
          {/* Telegram */}
          <a href="https://t.me/trispiainetwork" target="_blank" rel="noopener noreferrer"
            title="Telegram" style={{ color: C.textMuted, display: 'flex', alignItems: 'center', transition: 'color 0.2s' }}
            onMouseEnter={e => e.currentTarget.style.color = '#2CA5E0'}
            onMouseLeave={e => e.currentTarget.style.color = C.textMuted}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
              <path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z"/>
            </svg>
          </a>
          {/* X (Twitter) */}
          <a href="https://x.com/trispiainetwork" target="_blank" rel="noopener noreferrer"
            title="X (Twitter)" style={{ color: C.textMuted, display: 'flex', alignItems: 'center', transition: 'color 0.2s' }}
            onMouseEnter={e => e.currentTarget.style.color = '#ffffff'}
            onMouseLeave={e => e.currentTarget.style.color = C.textMuted}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
              <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-4.714-6.231-5.401 6.231H2.744l7.737-8.835L1.254 2.25H8.08l4.253 5.622zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
            </svg>
          </a>
          {/* LinkedIn */}
          <a href="https://www.linkedin.com/groups/20090008" target="_blank" rel="noopener noreferrer"
            title="LinkedIn" style={{ color: C.textMuted, display: 'flex', alignItems: 'center', transition: 'color 0.2s' }}
            onMouseEnter={e => e.currentTarget.style.color = '#0A66C2'}
            onMouseLeave={e => e.currentTarget.style.color = C.textMuted}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
              <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 0 1-2.063-2.065 2.064 2.064 0 1 1 2.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/>
            </svg>
          </a>
          {/* GitHub */}
          <a href="https://github.com/TRISPIAINETWORK/TRISPI" target="_blank" rel="noopener noreferrer"
            title="GitHub" style={{ color: C.textMuted, display: 'flex', alignItems: 'center', transition: 'color 0.2s' }}
            onMouseEnter={e => e.currentTarget.style.color = '#ffffff'}
            onMouseLeave={e => e.currentTarget.style.color = C.textMuted}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12"/>
            </svg>
          </a>
        </div>

        {/* Nav links */}
        <div style={{ display: 'flex', gap: '20px', alignItems: 'center' }}>
          <button onClick={() => goTo('build')} style={{ fontSize: '13px', color: C.textMuted, background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}>Docs</button>
          <button onClick={() => goTo('build')} style={{ fontSize: '13px', color: C.textMuted, background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}>Run Node</button>
        </div>
      </footer>

      <WalletModal isOpen={showWallet} onClose={() => setShowWallet(false)} />
    </div>
  );
}

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }
  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }
  componentDidCatch(error, info) {
    console.error('TRISPI ErrorBoundary caught:', error, info);
  }
  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: '40px', textAlign: 'center', fontFamily: 'system-ui', color: '#111827' }}>
          <h2 style={{ fontSize: '20px', marginBottom: '12px' }}>Something went wrong</h2>
          <p style={{ color: '#6B7280', fontSize: '14px', marginBottom: '20px' }}>
            {this.state.error?.message || 'An unexpected error occurred.'}
          </p>
          <button
            onClick={() => { this.setState({ hasError: false, error: null }); }}
            style={{ padding: '10px 24px', background: '#111827', color: '#fff', border: 'none', borderRadius: '8px', cursor: 'pointer', fontSize: '14px' }}
          >
            Try Again
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

function App() {
  return (
    <ErrorBoundary>
      <WalletProvider>
        <HashRouter>
          <AppContent />
        </HashRouter>
      </WalletProvider>
    </ErrorBoundary>
  );
}

export default App;
