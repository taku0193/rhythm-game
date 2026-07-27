<script setup>
import './assets/App.css';
import { onMounted, ref, reactive, watch, nextTick } from 'vue';
import { FilesetResolver, PoseLandmarker } from '@mediapipe/tasks-vision';

// === DOM要素 ===
const videoRef = ref(null);
const canvasRef = ref(null);
const audioPlayerRef = ref(null);

// === 全体的な状態 ===
const isLoading = ref(true);
const feedbackText = ref('モデルを読み込み中...');
const isGameActive = ref(false);
const showGameResults = ref(false);

// === ゲームロジックの状態 ===
const score = ref(0);
const level = ref(1);
const gameTime = ref(60);
const targetsHit = ref(0);
const totalTargets = ref(0);
const targets = ref([]);
const ripples = ref([]);
const hitFeedbackMessage = ref('');
const hitFeedbackColor = ref('');
const hitFeedbackFontSize = ref(60);
// 判定エフェクト用のアニメーション状態
const hitFeedbackScale = ref(1);
const hitFeedbackAlpha = ref(1);
let hitFeedbackTimer = null;
let hitFeedbackAnimTimer = null;
// スコア・コンボのアニメーション用
const scoreAnim = ref(false);
const comboAnim = ref(false);
const finalScore = ref(0);
const finalTargetsHit = ref(0);
const finalTotalTargets = ref(0);
const gameResultText = ref('');
const difficultySettings = {
  1: { targetCount: 3, targetRadius: 60, spawnInterval: 3000, gameTime: 60 },
  2: { targetCount: 5, targetRadius: 50, spawnInterval: 2500, gameTime: 60 },
  3: { targetCount: 7, targetRadius: 40, spawnInterval: 2000, gameTime: 60 }
};
const evaluationDistanceThresholds = { good: 50 };
const evaluationTimeThresholds = { perfect: 1000, good: 3000 };

// === BGM生成の状態 ===
const musicPrompt = ref('A cheerful and upbeat 80s synth-pop song');
const isGenerating = ref(false);
const bgmUrl = ref('');
const errorMessage = ref('');
const currentBpm = ref(null);
const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/+$/, '');

function apiUrl(path) {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  return `${apiBaseUrl}${normalizedPath}`;
}

// === 音響効果 ===
const audioContext = ref(null);
const sounds = ref({});
let poseLandmarker = null;
let canvasCtx = null;
let gameTimer = null;
let targetSpawnTimer = null;
let animationId = null;

// === ビート同期の視覚効果 ===
const beatCounter = ref(0);
const beatPhase = ref(0); // 0-1の範囲でビートの進行度を表す
const isBeatPulse = ref(false);
let beatTimer = null;
let gameStartTime = 0;

// === コンボシステム ===
const comboCount = ref(0);
const maxCombo = ref(0);
const comboMultiplier = ref(1);
const comboTimer = ref(null);
const comboTimeout = 2000; // 2秒でコンボリセット

// === 音楽視覚化 ===
const audioAnalyser = ref(null);
const frequencyData = ref(new Uint8Array(64));
const audioSource = ref(null);
const isAudioAnalyzing = ref(false);

// === スコアシステム強化 ===
const highScores = ref([]);
const gameStats = ref({
  totalGames: 0,
  totalScore: 0,
  averageScore: 0,
  bestCombo: 0,
  totalTargetsHit: 0,
  totalTargetsSpawned: 0
});

// === スコア管理 ---
function loadGameData() {
  try {
    const savedHighScores = localStorage.getItem('mediapipeGameHighScores');
    const savedStats = localStorage.getItem('mediapipeGameStats');
    
    if (savedHighScores) {
      highScores.value = JSON.parse(savedHighScores);
    }
    
    if (savedStats) {
      gameStats.value = JSON.parse(savedStats);
    }
  } catch (error) {
    console.error('ゲームデータの読み込みに失敗:', error);
  }
}

function saveGameData() {
  try {
    localStorage.setItem('mediapipeGameHighScores', JSON.stringify(highScores.value));
    localStorage.setItem('mediapipeGameStats', JSON.stringify(gameStats.value));
  } catch (error) {
    console.error('ゲームデータの保存に失敗:', error);
  }
}

function updateHighScores(score, level, combo) {
  const newScore = {
    score,
    level,
    combo,
    date: new Date().toLocaleDateString(),
    timestamp: Date.now()
  };
  
  highScores.value.push(newScore);
  highScores.value.sort((a, b) => b.score - a.score);
  highScores.value = highScores.value.slice(0, 10); // 上位10位まで
  
  saveGameData();
}

function updateGameStats(score, targetsHit, totalTargets, maxCombo) {
  gameStats.value.totalGames++;
  gameStats.value.totalScore += score;
  gameStats.value.averageScore = Math.round(gameStats.value.totalScore / gameStats.value.totalGames);
  gameStats.value.bestCombo = Math.max(gameStats.value.bestCombo, maxCombo);
  gameStats.value.totalTargetsHit += targetsHit;
  gameStats.value.totalTargetsSpawned += totalTargets;
  
  saveGameData();
}

// --- 初期化処理 ---
onMounted(async () => {
  await createPoseLandmarker();
  initAudio();
  loadGameData(); // ゲームデータを読み込み
  const video = videoRef.value;
  const canvas = canvasRef.value;
  canvasCtx = canvas.getContext('2d');
  if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: 'user' } });
      video.srcObject = stream;
      video.addEventListener('loadedmetadata', () => {
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        if (!isGameActive.value) { predictWebcam(); }
      });
    } catch (error) { console.error("カメラへのアクセスに失敗しました。", error); feedbackText.value = 'カメラにアクセスできません。'; }
  } else { feedbackText.value = 'このブラウザはカメラをサポートしていません。'; }
});

// --- MediaPipe初期化 ---
async function createPoseLandmarker() {
  try {
    const vision = await FilesetResolver.forVisionTasks("https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.35/wasm");
    poseLandmarker = await PoseLandmarker.createFromOptions(vision, {
      baseOptions: {
        modelAssetPath: `https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task`,
        delegate: "GPU"
      },
      runningMode: "VIDEO",
      numPoses: 1
    });
    isLoading.value = false;
    feedbackText.value = '準備OK！';
  } catch (error) { console.error('MediaPipe初期化エラー:', error); feedbackText.value = 'MediaPipeの初期化に失敗しました。'; }
}

// --- 音響ロジック ---
function initAudio() {
  try {
    audioContext.value = new (window.AudioContext || window.webkitAudioContext)();
    sounds.value = {
      perfect: createTone(880, 0.2, 'sine'),
      good: createTone(660, 0.2, 'triangle'),
      bad: createTone(330, 0.2, 'sawtooth'),
      levelUp: createTone(1046, 0.5, 'sine')
    };
  } catch (error) { console.log('音響効果が利用できません:', error); }
}
function createTone(frequency, duration, type) {
  return () => {
    if (!audioContext.value) return;
    const oscillator = audioContext.value.createOscillator();
    const gainNode = audioContext.value.createGain();
    oscillator.connect(gainNode);
    gainNode.connect(audioContext.value.destination);
    oscillator.frequency.value = frequency;
    oscillator.type = type;
    gainNode.gain.setValueAtTime(0.3, audioContext.value.currentTime);
    gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.value.currentTime + duration);
    oscillator.start(audioContext.value.currentTime);
    oscillator.stop(audioContext.value.currentTime + duration);
  };
}
function playSound(soundName) { if (sounds.value[soundName]) { sounds.value[soundName](); } }

// --- ゲーム制御ロジック ---
function calculateBpmBasedInterval(bpm) {
  if (!bpm) return difficultySettings[level.value].spawnInterval;
  // BPMから1拍の時間を計算（ミリ秒）
  const beatInterval = (60 / bpm) * 1000;
  // レベルに応じて拍数を調整（レベル1: 2拍、レベル2: 1.5拍、レベル3: 1拍）
  const beatMultiplier = { 1: 2, 2: 1.5, 3: 1 }[level.value] || 1;
  return Math.round(beatInterval * beatMultiplier);
}

function startGame() {
  showGameResults.value = false;
  isGameActive.value = true;
  score.value = 0; targetsHit.value = 0; totalTargets.value = 0; targets.value = [];
  gameTime.value = difficultySettings[level.value].gameTime;
  
  // コンボシステムをリセット
  resetCombo();
  
  // BPMに基づいてターゲット出現間隔を計算
  const spawnInterval = calculateBpmBasedInterval(currentBpm.value);
  console.log(`BPM: ${currentBpm.value}, 出現間隔: ${spawnInterval}ms`);
  
  // ビート同期の初期化
  if (currentBpm.value) {
    gameStartTime = Date.now();
    beatCounter.value = 0;
    beatPhase.value = 0;
    isBeatPulse.value = false;
    
    // ビートタイマーを開始
    const beatInterval = (60 / currentBpm.value) * 1000;
    beatTimer = setInterval(() => {
      beatCounter.value++;
      isBeatPulse.value = true;
      // ビートパルス時に軽い音響効果を追加
      // if (sounds.value.good) {
      //   sounds.value.good();
      // }
      setTimeout(() => { isBeatPulse.value = false; }, 100); // パルス効果を100msで消す
    }, beatInterval);
  }
  
  spawnTarget();
  targetSpawnTimer = setInterval(spawnTarget, spawnInterval);
  
  gameTimer = setInterval(() => {
    gameTime.value--;
    if (gameTime.value <= 0) { endGame(); }
  }, 1000);
  if (!animationId) predictWebcam();
}
function endGame() {
  isGameActive.value = false;
  clearInterval(gameTimer);
  clearInterval(targetSpawnTimer);
  if (beatTimer) {
    clearInterval(beatTimer);
    beatTimer = null;
  }
  if (comboTimer.value) {
    clearTimeout(comboTimer.value);
    comboTimer.value = null;
  }
  cancelAnimationFrame(animationId);
  animationId = null;
  finalScore.value = score.value;
  finalTargetsHit.value = targetsHit.value;
  finalTotalTargets.value = totalTargets.value;
  if (score.value >= level.value * 500 && level.value < 3) {
    level.value++;
    playSound('levelUp');
    gameResultText.value = `レベル ${level.value} にアップ！`;
  } else if (score.value >= level.value * 500 && level.value === 3) {
    gameResultText.value = `全レベルクリア！おめでとう！`;
  } else {
    gameResultText.value = `ゲーム終了！`;
  }
  showGameResults.value = true;
  updateHighScores(score.value, level.value, maxCombo.value);
  updateGameStats(score.value, targetsHit.value, totalTargets.value, maxCombo.value);
}
function changeLevel(newLevel) { if (!isGameActive.value) { level.value = newLevel; } }
function retryGame() { showGameResults.value = false; startGame(); }

// --- ターゲット&当たり判定ロジック ---
function spawnTarget() {
  if (!isGameActive.value || targets.value.length >= difficultySettings[level.value].targetCount) return;
  const canvas = canvasRef.value;
  if (!canvas) return;
  const margin = 100;
  const x = Math.random() * (canvas.width - 2 * margin) + margin;
  const y = Math.random() * (canvas.height - 2 * margin) + margin;
  // ノーツの種類をランダムで決定（60%通常, 40%スライド）
  const rand = Math.random();
  let type = 'normal';
  if (rand > 0.6) type = 'slide';
  let color = '#FF6347'; // 通常:赤
  if (type === 'slide') color = '#27ae60'; // スライド:緑
  let target = {
    id: Date.now() + Math.random(),
    x, y,
    radius: difficultySettings[level.value].targetRadius,
    color,
    type,
    hit: false, spawnTime: Date.now(),
    lifetime: 3000 // 3秒後に自動削除
  };
  if (type === 'slide') {
    // 終点をランダムに生成（始点から一定距離離す）
    const angle = Math.random() * 2 * Math.PI;
    const dist = 120 + Math.random() * 80;
    const ex = Math.max(margin, Math.min(canvas.width - margin, x + Math.cos(angle) * dist));
    const ey = Math.max(margin, Math.min(canvas.height - margin, y + Math.sin(angle) * dist));
    target.ex = ex;
    target.ey = ey;
    // 曲線用の制御点（始点と終点の間をランダムにずらす）
    const cx = (x + ex) / 2 + (Math.random() - 0.5) * 100;
    const cy = (y + ey) / 2 + (Math.random() - 0.5) * 100;
    target.cx = cx;
    target.cy = cy;
    target.slideStarted = false;
    target.slideStartTime = null;
    target.slideTrail = [];
  }
  targets.value.push(target);
  totalTargets.value++;
}
function evaluateHit(distance, spawnTime) {
  const timeToHit = Date.now() - spawnTime;
  if (distance <= evaluationDistanceThresholds.good) {
    if (timeToHit <= evaluationTimeThresholds.perfect) return 'perfect';
    if (timeToHit <= evaluationTimeThresholds.good) return 'good';
    return 'bad';
  }
  return 'none';
}
function applyTargetHit(target, evaluation) {
  target.hit = true;
  targetsHit.value++;
  if (hitFeedbackTimer) clearTimeout(hitFeedbackTimer);
  if (hitFeedbackAnimTimer) clearTimeout(hitFeedbackAnimTimer);
  
  // 基本スコアにコンボ倍率を適用
  const baseScore = ({ perfect: 100, good: 50, bad: 10 })[evaluation] || 0;
  const finalScore = Math.round(baseScore * comboMultiplier.value);
  score.value += finalScore;
  
  // 特殊ターゲット用の音響効果
  let soundEffect = evaluation;
  playSound(soundEffect);
  
  const feedback = {
    perfect: { msg: 'PERFECT!', color: '#FFD700', size: 80 },
    good: { msg: 'Good!', color: 'lime', size: 70 },
    bad: { msg: 'Bad...', color: 'orange', size: 60 }
  }[evaluation];
  
  // 特殊ターゲット用のメッセージ
  let message = feedback.msg;
  
  target.color = feedback.color;
  hitFeedbackMessage.value = message;
  hitFeedbackColor.value = feedback.color;
  hitFeedbackFontSize.value = feedback.size;
  hitFeedbackScale.value = 1.5;
  hitFeedbackAlpha.value = 1;
  // 判定メッセージのアニメーション
  let animFrame = 0;
  function animateFeedback() {
    animFrame++;
    hitFeedbackScale.value = 1.5 - 0.5 * (animFrame / 20);
    hitFeedbackAlpha.value = 1 - (animFrame / 30);
    if (animFrame < 30) {
      hitFeedbackAnimTimer = setTimeout(animateFeedback, 16);
    } else {
      hitFeedbackMessage.value = '';
      hitFeedbackScale.value = 1;
      hitFeedbackAlpha.value = 1;
    }
  }
  animateFeedback();
  setTimeout(() => {
    const index = targets.value.findIndex(t => t.id === target.id);
    if (index > -1) targets.value.splice(index, 1);
  }, 500);
  
  // 波紋エフェクトを追加
  ripples.value.push({
    x: target.x,
    y: target.y,
    startTime: Date.now(),
    color: feedback.color,
    duration: 600, // 波紋の寿命(ms)
    maxRadius: target.radius * 2.5
  });
  // スコア・コンボのアニメーション
  scoreAnim.value = true;
  comboAnim.value = true;
  setTimeout(() => { scoreAnim.value = false; }, 200);
  setTimeout(() => { comboAnim.value = false; }, 200);
}

// --- BGM生成ロジック ---
async function handleGenerateBgm() {
  if (!musicPrompt.value.trim() || isGenerating.value) return;
  isGenerating.value = true;
  errorMessage.value = '';
  bgmUrl.value = '';
  try {
    console.log('BGM生成リクエストを送信中...');
    const response = await fetch(apiUrl('/generate-bgm'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt: musicPrompt.value, duration: 30 })
    });
    
    console.log('レスポンス受信:', response.status, response.statusText);
    
    if (!response.ok) {
      const errorText = await response.text();
      console.error('サーバーエラー詳細:', errorText);
      throw new Error(`サーバーエラー: ${response.status} ${response.statusText}`);
    }
    
    const data = await response.json();
    console.log('レスポンスデータ:', data);
    
    if (data.success) {
      const audioPath = new URL(data.url, window.location.origin).pathname;
      bgmUrl.value = apiUrl(audioPath);
      currentBpm.value = data.bpm;
      console.log('BGM URL設定:', bgmUrl.value);
      
      // 音声ファイルの存在確認
      const filename = audioPath.split('/').pop();
      try {
        const checkResponse = await fetch(apiUrl(`/check-audio/${encodeURIComponent(filename)}`));
        const checkData = await checkResponse.json();
        console.log('音声ファイル確認結果:', checkData);
        if (!checkData.exists) {
          console.error('音声ファイルが見つかりません:', checkData.path);
          errorMessage.value = '音声ファイルが見つかりません。';
        } else {
          console.log(`音声ファイル確認OK: ${checkData.size} bytes`);
          // ファイルサイズが小さすぎる場合は警告
          if (checkData.size < 1000) {
            console.warn('音声ファイルが小さすぎます:', checkData.size, 'bytes');
            errorMessage.value = '音声ファイルが小さすぎる可能性があります。';
          }
          
          // WAVファイルの詳細テスト
          try {
            const testResponse = await fetch(apiUrl(`/test-audio/${encodeURIComponent(filename)}`));
            const testData = await testResponse.json();
            console.log('WAVファイル詳細テスト:', testData);
            if (!testData.is_valid_wav) {
              console.error('WAVファイルが無効です:', testData.header_info);
              errorMessage.value = 'WAVファイルが無効です。';
            }
          } catch (testError) {
            console.error('WAVファイルテストエラー:', testError);
          }
        }
      } catch (checkError) {
        console.error('音声ファイル確認エラー:', checkError);
      }
    } else {
      throw new Error(data.error || 'BGMの生成に失敗しました。');
    }
  } catch (error) {
    console.error('BGM生成エラー:', error);
    errorMessage.value = error.message;
  } finally {
    isGenerating.value = false;
  }
}
watch(bgmUrl, (newUrl) => {
  if (newUrl) {
    console.log('BGM URL変更検知:', newUrl);
    nextTick(() => {
      console.log('audioPlayerRef:', audioPlayerRef.value);
      if (audioPlayerRef.value) {
        console.log('音声再生を試行中...');
        
        // 音声要素の準備ができるまで待機
        const audio = audioPlayerRef.value;
        
        // 音声が読み込まれた後に再生を試行
        const tryPlay = () => {
          audio.play().then(() => {
            console.log('音声再生成功');
            errorMessage.value = '';
          }).catch(e => {
            console.error("BGMの自動再生に失敗:", e);
            if (e.name === 'NotAllowedError') {
              errorMessage.value = "ブラウザの制約により自動再生できませんでした。再生ボタンを押してください。";
            } else {
              errorMessage.value = `音声再生エラー: ${e.message}`;
            }
          });
        };
        
        // 音声が準備できている場合は即座に再生、そうでなければイベントを待つ
        if (audio.readyState >= 2) { // HAVE_CURRENT_DATA
          tryPlay();
        } else {
          audio.addEventListener('canplay', tryPlay, { once: true });
        }
        
        // 音声視覚化を初期化
        console.log('音声視覚化を初期化中...');
        initAudioVisualization(audioPlayerRef.value);
      } else {
        console.error('audioPlayerRefが見つかりません');
      }
    });
  }
});

// --- 描画ループ ---
function predictWebcam() {
  const video = videoRef.value;
  const canvas = canvasRef.value;
  if (!video || !canvas || video.readyState < 2 || !poseLandmarker) {
    animationId = requestAnimationFrame(predictWebcam);
    return;
  }
  const startTimeMs = performance.now();
  poseLandmarker.detectForVideo(video, startTimeMs, (results) => {
    canvasCtx.save();
    canvasCtx.clearRect(0, 0, canvas.width, canvas.height);
    
    // 音楽の強度に応じた背景色変化
    if (isAudioAnalyzing.value) {
      const intensity = getAudioIntensity();
      const hue = 200 + intensity * 60; // 青から紫への変化
      const saturation = 50 + intensity * 50;
      const lightness = 20 + intensity * 30;
      canvasCtx.fillStyle = `hsla(${hue}, ${saturation}%, ${lightness}%, 0.3)`;
      canvasCtx.fillRect(0, 0, canvas.width, canvas.height);
    }
    
    canvasCtx.scale(-1, 1);
    canvasCtx.translate(-canvas.width, 0);
    canvasCtx.drawImage(video, 0, 0, canvas.width, canvas.height);
    canvasCtx.restore();

    if (isGameActive.value) {
      // スコア表示アニメーション
      canvasCtx.font = scoreAnim.value ? "bold 38px Arial" : "bold 30px Arial";
      canvasCtx.fillStyle = scoreAnim.value ? "#FFD700" : "white";
      canvasCtx.textAlign = "left";
      canvasCtx.fillText(`Score: ${score.value}`, 20, 40);
      canvasCtx.fillText(`Level: ${level.value}`, 20, 80);
      canvasCtx.fillText(`Time: ${gameTime.value}s`, 20, 120);
      
      // ビートカウンターを表示
      if (currentBpm.value) {
        canvasCtx.font = "bold 25px Arial";
        canvasCtx.fillStyle = isBeatPulse.value ? "#FFD700" : "white";
        canvasCtx.fillText(`Beat: ${beatCounter.value}`, 20, 160);
        canvasCtx.fillText(`BPM: ${currentBpm.value}`, 20, 190);
      }
      
      // コンボ情報を表示
      if (comboCount.value > 0) {
        canvasCtx.font = comboAnim.value ? "bold 36px Arial" : "bold 28px Arial";
        canvasCtx.fillStyle = comboMultiplier.value > 1 ? "#FFD700" : "#FF6347";
        canvasCtx.fillText(`Combo: ${comboCount.value}`, 20, 220);
        if (comboMultiplier.value > 1) {
          canvasCtx.fillText(`x${comboMultiplier.value.toFixed(1)}`, 20, 250);
        }
      }
    }
    targets.value.forEach(target => {
      // 3秒経過したターゲットを自動削除
      if (!target.hit && Date.now() - target.spawnTime > target.lifetime) {
        const index = targets.value.findIndex(t => t.id === target.id);
        if (index > -1) targets.value.splice(index, 1);
        return; // このターゲットは描画しない
      }
      canvasCtx.save();
      let radius = target.radius;
      let alpha = 1.0;
      // ノーツの種類ごとに描画を分岐
      if (target.type === 'slide') {
        // 曲線スライドノーツ: 緑色の始点・終点と曲線
        // 曲線（ベジェ）
        canvasCtx.beginPath();
        canvasCtx.moveTo(target.x, target.y);
        canvasCtx.quadraticCurveTo(target.cx, target.cy, target.ex, target.ey);
        canvasCtx.strokeStyle = '#27ae60';
        canvasCtx.lineWidth = 5;
        canvasCtx.globalAlpha = 0.7;
        canvasCtx.stroke();
        // 始点
        canvasCtx.beginPath();
        canvasCtx.arc(target.x, target.y, radius, 0, 2 * Math.PI);
        canvasCtx.strokeStyle = '#27ae60';
        canvasCtx.lineWidth = 6;
        canvasCtx.globalAlpha = 1.0;
        canvasCtx.stroke();
        canvasCtx.beginPath();
        canvasCtx.arc(target.x, target.y, radius - 8, 0, 2 * Math.PI);
        canvasCtx.fillStyle = '#58d68d';
        canvasCtx.globalAlpha = 0.7;
        canvasCtx.fill();
        // 終点
        canvasCtx.beginPath();
        canvasCtx.arc(target.ex, target.ey, radius * 0.8, 0, 2 * Math.PI);
        canvasCtx.strokeStyle = '#229954';
        canvasCtx.lineWidth = 4;
        canvasCtx.globalAlpha = 1.0;
        canvasCtx.stroke();
        canvasCtx.beginPath();
        canvasCtx.arc(target.ex, target.ey, radius * 0.6, 0, 2 * Math.PI);
        canvasCtx.fillStyle = '#82e0aa';
        canvasCtx.globalAlpha = 0.7;
        canvasCtx.fill();
        // 矢印（終点側）
        const dx = target.ex - target.cx;
        const dy = target.ey - target.cy;
        const len = Math.sqrt(dx*dx + dy*dy);
        if (len > 0) {
          const ux = dx / len, uy = dy / len;
          const arrowLen = 18, arrowWidth = 8;
          const ax = target.ex - ux * (radius * 0.8);
          const ay = target.ey - uy * (radius * 0.8);
          canvasCtx.beginPath();
          canvasCtx.moveTo(ax, ay);
          canvasCtx.lineTo(ax - uy * arrowWidth - ux * arrowLen, ay + ux * arrowWidth - uy * arrowLen);
          canvasCtx.lineTo(ax + uy * arrowWidth - ux * arrowLen, ay - ux * arrowWidth - uy * arrowLen);
          canvasCtx.closePath();
          canvasCtx.fillStyle = '#229954';
          canvasCtx.globalAlpha = 1.0;
          canvasCtx.fill();
        }
        // スライド中の軌跡を描画
        if (target.slideStarted && !target.hit && target.slideTrail && target.slideTrail.length > 1) {
          canvasCtx.save();
          canvasCtx.beginPath();
          canvasCtx.moveTo(target.slideTrail[0].x, target.slideTrail[0].y);
          for (let i = 1; i < target.slideTrail.length; i++) {
            canvasCtx.lineTo(target.slideTrail[i].x, target.slideTrail[i].y);
          }
          canvasCtx.strokeStyle = 'rgba(46, 204, 113, 0.7)';
          canvasCtx.lineWidth = 8;
          canvasCtx.stroke();
          canvasCtx.restore();
        }
      } else {
        // 通常ノーツ: 赤色の円
        canvasCtx.beginPath();
        canvasCtx.arc(target.x, target.y, radius, 0, 2 * Math.PI);
        canvasCtx.strokeStyle = target.color;
        canvasCtx.globalAlpha = alpha;
        canvasCtx.lineWidth = 5;
        canvasCtx.stroke();
      }
      canvasCtx.globalAlpha = 1.0;
      canvasCtx.restore();
    });
    
    // スペクトラムアナライザーの描画
    if (isAudioAnalyzing.value && frequencyData.value) {
      const barWidth = canvas.width / frequencyData.value.length;
      const barHeight = 60;
      const startY = canvas.height - barHeight - 20;
      
      frequencyData.value.forEach((value, index) => {
        const barHeight = (value / 255) * 60;
        const x = index * barWidth;
        const y = startY + (60 - barHeight);
        
        // 周波数帯域に応じた色
        const hue = (index / frequencyData.value.length) * 360;
        canvasCtx.fillStyle = `hsl(${hue}, 70%, 60%)`;
        canvasCtx.fillRect(x, y, barWidth - 1, barHeight);
      });
    }
    
    // 波紋エフェクトの描画
    const now = Date.now();
    ripples.value = ripples.value.filter(ripple => {
      const elapsed = now - ripple.startTime;
      if (elapsed > ripple.duration) return false;
      const progress = elapsed / ripple.duration;
      const radius = 20 + (ripple.maxRadius - 20) * progress;
      const alpha = 0.4 * (1 - progress);
      canvasCtx.save();
      canvasCtx.beginPath();
      canvasCtx.arc(ripple.x, ripple.y, radius, 0, 2 * Math.PI);
      canvasCtx.strokeStyle = ripple.color;
      canvasCtx.globalAlpha = alpha;
      canvasCtx.lineWidth = 6;
      canvasCtx.stroke();
      canvasCtx.globalAlpha = 1.0;
      canvasCtx.restore();
      return true;
    });
    
    // 判定メッセージのアニメーション描画
    if (hitFeedbackMessage.value) {
      canvasCtx.save();
      canvasCtx.font = `bold ${hitFeedbackFontSize.value * hitFeedbackScale.value}px Arial`;
      canvasCtx.globalAlpha = hitFeedbackAlpha.value;
      canvasCtx.fillStyle = hitFeedbackColor.value;
      canvasCtx.textAlign = "center";
      canvasCtx.fillText(hitFeedbackMessage.value, canvas.width / 2, canvas.height / 2);
      canvasCtx.globalAlpha = 1.0;
      canvasCtx.restore();
    }
    
    if (results.landmarks && results.landmarks.length > 0) {
      const wrists = results.landmarks[0].filter((_, i) => i === 15 || i === 16);
      wrists.forEach((wrist, index) => {
        if (wrist.visibility > 0.5) {
          const wristX = (1 - wrist.x) * canvas.width;
          const wristY = wrist.y * canvas.height;
          // 手首の点を描画
          canvasCtx.beginPath();
          canvasCtx.arc(wristX, wristY, 15, 0, 2 * Math.PI);
          canvasCtx.fillStyle = index === 0 ? 'purple' : 'blue';
          canvasCtx.fill();
          // 判定ロジック
          targets.value.forEach(target => {
            if (!target.hit) {
              if (target.type === 'slide') {
                if (target.slideStarted && !target.hit) {
                  if (!target.slideTrail) target.slideTrail = [];
                  target.slideTrail.push({ x: wristX, y: wristY });
                  if (target.slideTrail.length > 30) target.slideTrail.shift();
                  // 終点に到達したか判定
                  const distEnd = Math.sqrt(Math.pow(target.ex - wristX, 2) + Math.pow(target.ey - wristY, 2));
                  if (distEnd <= target.radius * 0.8) {
                    const elapsed = Date.now() - target.slideStartTime;
                    let evaluation = 'bad';
                    if (elapsed <= 1000) evaluation = 'perfect';
                    else if (elapsed <= 2000) evaluation = 'good';
                    applyTargetHit(target, evaluation);
                  }
                } else if (!target.slideStarted) {
                  // 始点に触れたか
                  const distStart = Math.sqrt(Math.pow(target.x - wristX, 2) + Math.pow(target.y - wristY, 2));
                  if (distStart <= target.radius) {
                    target.slideStarted = true;
                    target.slideStartTime = Date.now();
                  }
                }
              } else {
                // 通常ノーツ
                const distance = Math.sqrt(Math.pow(target.x - wristX, 2) + Math.pow(target.y - wristY, 2));
                const evaluation = evaluateHit(distance, target.spawnTime);
                if (evaluation !== 'none') { applyTargetHit(target, evaluation); }
              }
            }
          });
        }
      });
    }
  });
  animationId = requestAnimationFrame(predictWebcam);
}

// --- 音楽視覚化 ---
function initAudioVisualization(audioElement) {
  if (!audioContext.value || !audioElement) return;
  
  try {
    // 音声ソースを作成
    audioSource.value = audioContext.value.createMediaElementSource(audioElement);
    
    // アナライザーを作成
    audioAnalyser.value = audioContext.value.createAnalyser();
    audioAnalyser.value.fftSize = 128;
    audioAnalyser.value.smoothingTimeConstant = 0.8;
    
    // 接続
    audioSource.value.connect(audioAnalyser.value);
    audioAnalyser.value.connect(audioContext.value.destination);
    
    isAudioAnalyzing.value = true;
    updateAudioVisualization();
  } catch (error) {
    console.error('音声視覚化の初期化に失敗:', error);
  }
}

function updateAudioVisualization() {
  if (!isAudioAnalyzing.value || !audioAnalyser.value) return;
  
  audioAnalyser.value.getByteFrequencyData(frequencyData.value);
  requestAnimationFrame(updateAudioVisualization);
}

function getAudioIntensity() {
  if (!frequencyData.value || frequencyData.value.length === 0) return 0;
  
  // 低周波数帯域の平均値を計算
  const lowFreqSum = frequencyData.value.slice(0, 16).reduce((sum, val) => sum + val, 0);
  return lowFreqSum / 16 / 255; // 0-1の範囲に正規化
}

// --- コンボシステム ---
function startCombo() {
  comboCount.value++;
  maxCombo.value = Math.max(maxCombo.value, comboCount.value);
  
  // コンボ倍率の計算（10コンボごとに倍率アップ）
  comboMultiplier.value = 1 + Math.floor(comboCount.value / 10) * 0.5;
  
  // コンボタイマーをリセット
  if (comboTimer.value) clearTimeout(comboTimer.value);
  comboTimer.value = setTimeout(() => {
    comboCount.value = 0;
    comboMultiplier.value = 1;
  }, comboTimeout);
  
  // コンボボーナス音を再生
  if (comboCount.value >= 5) {
    playSound('levelUp'); // 高コンボ時はレベルアップ音
  }
}

function resetCombo() {
  comboCount.value = 0;
  comboMultiplier.value = 1;
  if (comboTimer.value) {
    clearTimeout(comboTimer.value);
    comboTimer.value = null;
  }
}

// --- 音声制御機能 ---
function playAudio() {
  if (audioPlayerRef.value) {
    // AudioContextがsuspendedならresume
    if (audioContext.value && audioContext.value.state === "suspended") {
      audioContext.value.resume();
    }
    console.log('手動再生を試行中...');
    audioPlayerRef.value.play().then(() => {
      console.log('手動再生成功');
      errorMessage.value = '';
    }).catch(e => {
      console.error('手動再生失敗:', e);
      errorMessage.value = `手動再生エラー: ${e.message}`;
    });
  }
}

function pauseAudio() {
  if (audioPlayerRef.value) {
    console.log('音声停止');
    audioPlayerRef.value.pause();
  }
}

function goHome() {
  window.location.reload();
}
</script>

<template>
  <div id="container">
    <div class="video-container">
      <video ref="videoRef" autoplay playsinline></video>
      <canvas ref="canvasRef"></canvas>
      <!-- BGM用audioは常にDOMに存在し、UIからは非表示 -->
      <audio
        :src="bgmUrl"
        ref="audioPlayerRef"
        class="hidden-audio"
        loop
        preload="auto"
        crossorigin="anonymous"
      ></audio>
      <!-- 重ねるパネル -->
      <div
        class="overlay-panel"
        v-if="!isGameActive && !showGameResults"
      >
        <h1>🎯 AI Rhythmix</h1>
        <div v-if="isLoading" class="loading">{{ feedbackText }}</div>
        <div v-if="!isLoading" class="control-panel">
          <h3>BGM生成 (AI)</h3>
          <input
            type="text"
            v-model="musicPrompt"
            placeholder="例: 80s pop song with synth"
            :disabled="isGenerating"
          />
          <button @click="handleGenerateBgm" :disabled="isGenerating">
            {{ isGenerating ? '生成中...' : 'BGMを生成' }}
          </button>
          <p v-if="isGenerating" class="loading-text">BGMを生成中です... (数分かかります)</p>
          <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>
          <div v-if="bgmUrl" class="audio-controls">
            <button @click="playAudio" class="play-button">▶ 再生</button>
            <button @click="pauseAudio" class="pause-button">⏸ 停止</button>
          </div>
          <p v-if="currentBpm" class="bpm-info">
            🎵 解析されたBPM: <strong>{{ currentBpm }}</strong>
          </p>
        </div>
        <div v-if="!isLoading && !isGameActive && !showGameResults" class="menu">
          <h2>レベル選択</h2>
          <div class="level-buttons">
            <button 
              v-for="lvl in 3" 
              :key="lvl"
              :class="{ active: level === lvl }"
              @click="changeLevel(lvl)"
            >
              レベル {{ lvl }}
            </button>
          </div>
          <div class="level-info">
            <h3>レベル {{ level }} の設定</h3>
            <p>ターゲット数: {{ difficultySettings[level].targetCount }}</p>
            <p>ターゲットサイズ: {{ difficultySettings[level].targetRadius }}px</p>
            <p v-if="currentBpm">
              出現間隔: {{ (calculateBpmBasedInterval(currentBpm) / 1000).toFixed(1) }}秒 (BPM {{ currentBpm }} ベース)
            </p>
            <p v-else>
              出現間隔: {{ difficultySettings[level].spawnInterval / 1000 }}秒 (デフォルト)
            </p>
          </div>
          <button class="start-button" @click="startGame">ゲーム開始</button>
        </div>
      </div>
      <div v-if="showGameResults" class="overlay-panel">
        <h1>🎯 AI Rhythmix</h1>
        <div class="game-results">
          <h2>ゲーム結果</h2>
          <p class="result-message">{{ gameResultText }}</p>
          <p>最終スコア: <span class="highlight-score">{{ finalScore }}</span></p>
          <p>ヒットしたターゲット: {{ finalTargetsHit }} / {{ finalTotalTargets }}</p>
          <p v-if="maxCombo > 0">最大コンボ: <span class="highlight-combo">{{ maxCombo }}</span></p>
          <div v-if="highScores.length > 0" class="high-scores">
            <h3>ハイスコア</h3>
            <table class="score-table">
              <thead>
                <tr>
                  <th>順位</th>
                  <th>スコア</th>
                  <th>レベル</th>
                  <th>コンボ</th>
                  <th>日付</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(score, index) in highScores.slice(0, 5)" :key="index">
                  <td class="rank">{{ index + 1 }}</td>
                  <td class="score">{{ score.score }}</td>
                  <td class="level">{{ score.level }}</td>
                  <td class="combo">{{ score.combo }}</td>
                  <td class="date">{{ score.date }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="stats">
            <!-- <h3>統計情報</h3> -->
            <p>総ゲーム数: {{ gameStats.totalGames }}</p>
            <p>平均スコア: {{ gameStats.averageScore }}</p>
            <p>最高コンボ: {{ gameStats.bestCombo }}</p>
            <p>総ヒット率: {{ gameStats.totalTargetsSpawned > 0 ? Math.round((gameStats.totalTargetsHit / gameStats.totalTargetsSpawned) * 100) : 0 }}%</p>
          </div>
          <button class="start-button" @click="goHome">ホームに戻る</button>
        </div>
      </div>
    </div>
  </div>
</template>
