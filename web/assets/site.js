/* AxVigil site behaviour: facts, language, nav, tabs, accordion. */
(function () {
  var factsEl = document.getElementById("axvigil-facts");
  var facts = {};
  try { facts = JSON.parse(factsEl.textContent); } catch (err) { facts = {}; }

  function get(path) {
    return String(path).split(".").reduce(function (obj, key) {
      return obj == null ? obj : obj[key];
    }, facts);
  }

  function formatFact(path, lang) {
    if (path === "stats.tests.detail") {
      var t = facts.stats.tests;
      return lang === "zh-TW"
        ? "合約 " + t.contracts + " · Python " + t.python
        : "contracts " + t.contracts + " · Python " + t.python;
    }
    var value = get(path);
    if (value == null) return "";
    if (/\.share$/.test(path)) return value + "%";
    if (path === "chain.gasUsed") return Number(value).toLocaleString("en-US");
    return String(value);
  }

  function bindFacts(lang) {
    document.querySelectorAll("[data-fact]").forEach(function (el) {
      el.textContent = formatFact(el.getAttribute("data-fact"), lang);
    });
    var explorer = facts.chain && facts.chain.explorer ? facts.chain.explorer : "https://testnet.bscscan.com";
    document.querySelectorAll("[data-fact-href]").forEach(function (el) {
      var path = el.getAttribute("data-fact-href");
      var value = get(path);
      if (!value) return;
      var kind = /Tx$/.test(path) ? "/tx/" : "/address/";
      el.setAttribute("href", explorer + kind + value);
    });
  }

  var ZH = {
    "skip": "跳至主要內容",
    "nav.road": "路線",
    "sec.home": "[:首頁]",
    "sec.problem": "[:問題]",
    "sec.how": "[:如何]",
    "sec.proof": "[:證明]",
    "sec.road": "[:路線]",
    "sec.faq": "[:問答]",
    "sec.board": "[:排行]",
    "board.h": "同樣的六個漏洞類型。",
    "board.lede": "四個 Muse Spark 參賽者，每個漏洞類型一枚 seed。muse-spark-1.1、1.2、1.3 解出 6/6。1.1 的 agentic 跑出 4/6。這次用了 114 次請求中的 83 次，2026-11-02，commit 2c45b7a。",
    "board.open": "打開排行",
    "nav.faq": "問答",
    "cta.records": "看鏈上紀錄",
    "cta.scan": "在 BscScan 查驗 ↗",
    "hero.kicker": "BSC 測試網 · 鏈 97",
    "stat.records": "已鑄造紀錄",
    "stat.recordsS": "三次門檻鑄造，加一次較早的簽名重放",
    "stat.families": "漏洞類型",
    "stat.familiesS": "每個類型二十道新變體",
    "stat.graded": "已評分的修復",
    "stat.gradedS": "這次公開寫下的通過",
    "stat.tests": "測試",
    "stat.testnet": "測試網",
    "problem.kicker": "01  問題",
    "problem.h": "算力花在謎題上，漏洞還在。",
    "problem.line": "Web3 仍把 AI 算力花在只為鑄一張紀念品的謎題上。AxVigil 把這份算力轉去修復漏洞。",
    "problem.s1": "2025 年 1 月到 12 月初被盜超過 34 億美元。最大的幾筆集中在私鑰基礎設施。",
    "problem.s2": "2025 年程式碼漏洞利用是發生次數最多的黑客類別（52 次、3.5 億美元）。",
    "problem.s3": "智能合約漏洞 5.12 億美元。上文的區間是 TRM 的程式碼漏洞利用總額與這份 Hacken 總額。",
    "how.kicker": "02  如何運作",
    "how.h": "四步，從題目到鏈上紀錄。",
    "how.s1t": "題目",
    "how.s1d": "一個漏洞類型加一枚種子，變成換名、重排過的新變體。代理拿不到類型、種子、隱藏測試或參考修復。",
    "how.s2t": "Muse Spark 修復",
    "how.s2d": "muse-spark-1.1 經 Meta Model API，在沙盒裡提出修補與概念驗證。它是第一個在這裡留下公開紀錄的模型。",
    "how.s3t": "確定性評分",
    "how.s3d": "四項檢查：概念驗證必須打穿原合約、修補後必須失敗、隱藏功能測試仍通過、改動停在上限內。",
    "how.s4t": "連署與紀錄",
    "how.s4d": "三位許可制驗證者裡的兩位簽名。一次鑄造寫入收藏，以及一枚鎖定的、跟著 Agent ID 的技能紀錄。",
    "proof.kicker": "03  證明",
    "proof.h": "鏈上的紀錄。",
    "proof.lede": "Muse Spark 是第一個留下公開紀錄的模型。下面四筆都在 BSC 測試網。三次在 2-of-3 收藏合約上，第一次請求就通過。較早的簽名重放在第一份收藏合約上，之後揭示為 LEGENDARY。",
    "proof.th1": "漏洞類型",
    "proof.th2": "紀錄",
    "proof.th3": "簽名",
    "proof.th4": "交易",
    "proof.r1": "門檻 token #1 · agent 8 · 第一次請求 · 5,067 completion tokens",
    "proof.r2": "門檻 token #2 · agent 9 · 第一次請求 · 3,336 completion tokens",
    "proof.r3": "門檻 token #3 · agent 10 · 第一次請求 · 4,560 completion tokens",
    "proof.r4": "第一份收藏 token #2 · agent 7 · 已揭示 LEGENDARY",
    "proof.fam1": "價格操縱",
    "proof.fam2": "權限控制",
    "proof.fam4": "簽名重放",
    "proof.note": "權限控制 seed 1 與橋的 seed 7 有評分，但不是這幾筆鑄造。參考解的冒煙測試是第一份收藏的 token #1，tier 為 COMMON，沒有算進上面的 4。三次門檻評分用的是子行程沙箱，不是 Docker。verify_evidence.py 對三個 CID 都是 OK。",
    "proof.reTitle": "重算這份證據",
    "proof.reNote": "一次評分會寫下 backend/evidence/<submissionHash>/manifest.json。這條指令檢查 CID、提交雜湊、種子承諾，並再跑一次評分器。下面用的是門檻 token #1 的提交雜湊。",
    "chip.testnet": "測試網",
    "chip.perm": "許可制 · 3 位驗證者 · 2-of-3",
    "chip.planned": "計畫中",
    "road.kicker": "04  路線",
    "road.h": "已上線的，以及還沒有的。",
    "road.t0": "階段 0 · BSC 測試網",
    "road.d0": "漏洞沙盒、隱藏測試評分、2-of-3 驗證者鑄造、證據 CID。三次 Muse Spark 門檻鑄造，verify_evidence.py 為 OK。實測評分用子行程沙箱。",
    "road.t1": "階段 1",
    "road.d1": "用真實的 agent 註冊表換掉 MockAgentID。外部審查評分器。揭示門檻批次。讓 Docker 沙箱跑實測評分。",
    "road.t2": "階段 2",
    "road.d2": "在真實協議上做掃描試點與賞金銜接。更多漏洞類型。開放的驗證者集合。",
    "road.t3": "階段 3 · 效用代幣",
    "road.d3": "只有多驗證者評分已上線，而且有真實付費需求，才會考慮。白皮書裡的設計，不是要約。目前沒有發行。",
    "flag.live": "已上線 · 測試網",
    "flag.plan": "計畫中",
    "flag.token": "計畫中，尚未發行",
    "faq.kicker": "05  問答",
    "faq.h": "直接的回答。",
    "faq.q1": "驗證者現在是誰？",
    "faq.a1": "三位，目前為許可制，由團隊運行。他們各自重評，只有自己的評分通過才簽名。這三次鑄造各送出兩份簽名。開放的驗證者集合是計畫，尚未上線。門檻合約的擁有者不是驗證者。",
    "faq.q2": "測試網紀錄有沒有金錢價值？",
    "faq.a2": "沒有。紀錄不能買、不能轉移。它不是收益，也不是對收入的主張。沒有發行代幣，本頁不是出售要約。",
    "faq.q3": "這算不算一次審計？",
    "faq.a3": "不算。通過的紀錄只表示：在一道受控的新變體上，修好了一個已知類型。它不是審計，也不表示代理找得到未知漏洞。",
    "faq.q4": "要怎麼重算？",
    "faq.a4": "拿證據包，跑 scripts/verify_evidence.py。它重算 CID 與提交雜湊、檢查種子承諾，並再評一次。三次門檻證據包都回了 OK。",
    "close.h": "紀錄在測試網上。可以重算。",
    "foot.docsLink": "文件",
    "foot.disc": "僅沙箱與測試網。未經審計。不要用於生產資金。沒有發行代幣，本頁也不是出售代幣的要約。技能紀錄不能購買或轉移。能力紀錄不是「agent 能找出未知漏洞」的主張。",
    "nav.menu": "選單",
    "nav.problem": "問題",
    "nav.how": "管線",
    "nav.muse": "模型",
    "nav.crucible": "熔爐",
    "nav.proof": "鏈上",
    "nav.trust": "信任",
    "nav.board": "排行",
    "nav.lang": "語言",
    "cta.demo": "試用 Demo",
    "cta.interactiveDemo": "啟動互動熔爐 Demo ↗",
    "cta.paper": "閱讀白皮書",
    "cta.github": "GitHub",
    "hero.note": "Hero strings live in axvigil-facts heroCopy, not here.",
    "stat.challenges": "挑戰",
    "stat.families": "漏洞類型",
    "stat.threshold": "驗證者門檻",
    "stat.thresholdS": "已上線的集合 · 三次 Muse Spark 鑄造",
    "bento.ch": "題庫裡的挑戰。六個漏洞類型，每個二十道變體。",
    "bento.proofT": "鏈上證明",
    "bento.proofD": "收藏 #2 與已鎖定的技能 #7，一次鑄造，一枚提交雜湊。",
    "bento.val": "Muse Spark 是第一個在這裡留下公開紀錄的模型。這三次都在第一次請求通過。兩位許可制驗證者簽名。verify_evidence.py 為 OK。評分用的是子行程沙箱。",
    "stat.checks": "評分檢查",
    "stat.tests": "通過的測試",
    "problem.kicker": "［問題］",
    "problem.h1": "看似合理的修補",
    "problem.h2": "不是已驗證的修復。",
    "problem.lede": "兩件事並排。AI 算力花在保護不了任何人的謎題上。合約安全無法規模化。缺的是一個任何人都能重跑的檢查。",
    "problem.c1t": "有算力，沒有防護",
    "problem.c1d": "許多 Web3 專案把代理指向數學題與哈希運算，再鑄一枚速度的紀念品。產出保護不了任何存款。",
    "vision.body": "AxVigil 想把 Web3 的 AI 算力，用在真正有意義的地方。現在有個荒謬的現象：越來越多項目讓 AI 代理去解數學題、算哈希，只為了鑄一張 NFT 或挖一個新代幣。算力燒掉了，鏈上卻沒有變得更安全。與此同時，加密產業每年被盜走數十億美元，2025 年超過 34 億。最大的幾筆多半來自私鑰與基礎設施被攻破，但智能合約程式碼漏洞仍是發生次數最多的攻擊類型，2025 年單這一類就造成約 3.5 億到 5 億美元的真實損失，而 AI 正在讓攻擊變得更便宜、更快。AxVigil 把這股算力導向這個真實的痛點：AI 代理在每次都會重新變形的漏洞沙盒裡修補合約，三個驗證者重新評分、至少兩個簽名同意，每一次成功的修補都在鏈上留下一份任何人都能重新計算的能力紀錄。協議在挑選 AI 掃描工具時，可以查證這些紀錄，而不只是聽廣告。我們不發空氣幣，也不搞零和遊戲。我們只想讓每一次 AI 推理，都朝保護鏈上資產多走一步。",
    "vision.s1": "2025 年 1 月到 12 月初被盜超過 34 億美元。最大的幾筆集中在私鑰基礎設施。",
    "vision.s2": "2025 年程式碼漏洞利用是發生次數最多的黑客類別（52 次、3.5 億美元）。基礎設施攻擊 45 次、22 億美元。",
    "vision.s3": "智能合約漏洞 5.12 億美元。上文的區間是 TRM 的程式碼漏洞利用總額與這份 Hacken 總額，取整之後。",
    "problem.c2t": "安全供不應求",
    "problem.c2d": "白皮書的描述：漏洞損失以數十億美元計，頂級審計排期數月、費用達五到六位數美元，許多小型協議未經審計就上線。",
    "problem.c3t": "沒有獨立檢查",
    "problem.c3d": "看似合理的 patch 不是修復。目前沒有可規模化、可重跑的方式，證明某個 agent 消除了漏洞、又沒有把合約改壞。",
    "sides.kicker": "［三方］",
    "sides.h1": "這是給誰的",
    "sides.h2": "今天，以及之後。",
    "sides.tabs": "對象",
    "sides.agents": "Agent",
    "sides.protocols": "協議",
    "sides.validators": "驗證者",
    "sides.aT": "解一道被發下來的變體。",
    "sides.aD": "Agent 用錢包簽章登入，簽章會對上 Agent ID 註冊表，只拿到原始碼，再交上修補與概念驗證。開啟獎勵場次就花掉兩次終身嘗試中的一次，過或不過都算。練習模式可以指定漏洞類型，不能拿鑄造。通過只能授權一次。",
    "sides.pT": "初篩，不是審計。",
    "sides.pD": "付費掃描、賞金分成與持續監控都還在計畫中，尚未建成。預期的付款方是協議的安全預算，以穩定幣或法幣支付。通過的紀錄只顯示 agent 能在受控目標上修好已知類別。它不顯示 agent 能找出未知漏洞。那個方向若做成，也是輔助，而不是取代人工審計。",
    "sides.vT": "自己再評一次，才簽名。",
    "sides.vD": "三位驗證者目前是許可制，由團隊運行。他們重評每一份證據包，只有自己的評分通過才簽名。三次 Muse Spark 鑄造各送出兩份簽章。開放的驗證者集合是計畫，尚未上線。質押與罰沒尚未建成。門檻收藏合約的擁有者不是驗證者。",
    "how.kicker": "［如何運作］",
    "how.h1": "從題目到憑證。",
    "how.h2": "沒有自稱。",
    "how.lede": "伺服器發變體。Agent 拿不到漏洞類型、種子、隱藏測試或參考修復。四項檢查都過，才可能被簽名。",
    "how.s1t": "題目",
    "how.s1d": "漏洞類型加種子，變成換名、重排過的變體。結構太像的會在發題前被丟掉。",
    "how.s2t": "Meta agent",
    "how.s2d": "muse-spark-1.1 經 Meta Model API 提出修補與概念驗證。失敗會以評分回饋送回。",
    "how.s3t": "驗證器",
    "how.s3d": "沙箱裡的四項確定性檢查。結果是一份正規 JSON，以及一枚提交雜湊。",
    "how.s4t": "驗證者",
    "how.s4d": "另一份收藏合約檢查 2-of-3 驗證者簽章。三次 Muse Spark 場次在那裡鑄造。較早的收藏合約仍是單一簽章者，而且那把金鑰已經從擁有者輪換出去。",
    "how.s5t": "憑證",
    "how.s5d": "一次鑄造同時寫入 ERC-721 收藏與 ERC-5192 技能紀錄。技能是鎖定的。它跟著 Agent ID，不跟著錢包。",
    "how.k1": "概念驗證必須打穿原始合約。假的 PoC 在這裡失敗。",
    "how.k2": "同一份概念驗證在修補後必須失敗。漏洞是真的消失了。",
    "how.k3": "隱藏的功能測試仍然通過。修復沒有把合約掏空。",
    "how.k4": "改動的行數與位元組停在上限內，公開介面必須留下來。",
    "flag.now": "本版本（測試網）",
    "flag.pending": "尚未廣播",
    "flag.live": "已在鏈上合約",
    "flag.liveBadge": "已上線",
    "flag.plan": "計畫中",
    "flag.road": "路線圖",
    "muse.kicker": "［Muse Spark · 第一個留下公開紀錄的模型］",
    "muse.h1": "真實模型回合。",
    "muse.h2": "不是排行榜。",
    "muse.lede": "muse-spark-1.1，經 Meta Model API（https://api.meta.ai/v1）。下表是這個版本寫下來的回合。completion tokens 是模型輸出，不是專案代幣。",
    "muse.cap": "前三列鑄在 2-of-3 收藏合約上。每個 CID 的 verify_evidence.py 都是 OK。評分用的是子行程沙箱，不是 Docker。簽章重放較早鑄在第一份收藏合約上，之後揭示為傳奇。橋的回合有評分，但不是那三次鑄造之一。",
    "muse.th1": "漏洞類型",
    "muse.th2": "結果",
    "muse.th3": "嘗試",
    "muse.t1n": "價格操縱",
    "muse.t1d": "第一次請求。5,067 個 completion tokens。2-of-3 簽章。CID bafkreick5qyty6dxfa6w6p2immr5jg2bj2buvvjvdeohnj7j2eui3fguly。verify_evidence.py 為 OK。",
    "muse.t2n": "權限控制",
    "muse.t2d": "第一次請求。3,336 個 completion tokens。2-of-3 簽章。CID bafkreib5fwr5qggt3wrxev7u7uhi4tvclkcgjhe4nf4hva7tsmfhhbmbcm。verify_evidence.py 為 OK。",
    "muse.t3n": "價格操縱",
    "muse.t3d": "第一次請求。4,560 個 completion tokens。2-of-3 簽章。CID bafkreidtrw73rx3b6rdvdl32qxlusrggsbijrfhdmnhofhch6zodaqzpoe。verify_evidence.py 為 OK。",
    "muse.r1n": "簽章重放",
    "muse.r1d": "第一次就過。1 次請求、4,947 個 completion tokens。鑄在 0x0658…4658，之後揭示為傳奇，artId 320000。",
    "muse.r2n": "權限控制",
    "muse.r2d": "隱藏測試改為接受未授權呼叫的任何 revert 之後，第一次就過。3,487 個 completion tokens，16 秒。",
    "muse.r3n": "橋接幽靈存款",
    "muse.r3d": "第 0 次：只擋 address(0)，隱藏測試 7/8。第 1 次：改為檢查 code.length，通過。16,250 個 completion tokens，45 秒。提示改寫之前，同一顆種子失敗了五次，都停在 7/8。",
    "cru.kicker": "［熔爐］",
    "cru.h1": "六個漏洞類型。",
    "cru.h2": "一百二十道變體。",
    "cru.lede": "每個漏洞類型是一類漏洞。種子會換掉識別字、插入干擾函式、重排函式本體。每個漏洞類型出二十道不重複的變體，參考解要先通過評分才算數。其中兩個漏洞類型依已修補、已公開的事件重建。沒有複製協議原始碼。",
    "m1.n": "重入",
    "m1.m": "基礎 · 類別 0",
    "m1.d": "提款先把金額送出，才清掉餘額。類別修復是檢查—效果—互動：先把餘額歸零。二十道變體。",
    "m2.n": "價格操縱",
    "m2.m": "進階 · 類別 1",
    "m2.d": "抵押品用一筆交易裡就能被兌換推動的現貨價格計價。類別修復是改讀抗操縱的參考價。二十道變體。",
    "m3.n": "權限控制",
    "m3.m": "基礎 · 類別 2",
    "m3.d": "金庫掃款沒有擁有者檢查。類別修復是把它限制給擁有者。隱藏測試接受未授權呼叫的任何 revert，所以角色被換名仍然算過。二十道變體。",
    "m4.n": "簽章重放",
    "m4.m": "傳奇 · 類別 2",
    "m4.d": "已簽名的憑證沒有被標記為用過，同一份簽章可以再把金庫搬空。類別修復是簽章檢查後記下摘要。這是傳奇難度的權限控制漏洞類型，也是 Muse Spark 鑄造的那一題。二十道變體。",
    "m5.n": "橋接幽靈存款",
    "m5.d": "Qubit QBridge，2022 年 1 月 27 至 28 日，依公開描述重建。對沒有程式碼的位址做存款拉取會「成功」，於是一筆什麼都沒搬走的存款，之後可以當成真的代幣提走。只有拒絕無程式碼的代幣才算過。只擋 address(0) 會被隱藏測試打掉。漏洞類型上記錄的損失約 8,000 萬美元（rekt.news、CertiK）。進階，類別 2。二十道變體。",
    "m6.n": "空市場份額膨脹",
    "m6.d": "Hundred Finance（2023 年 4 月）與 Sonne（2024 年 5 月）的 Compound 分叉空市場類別，無分叉重建。捐贈把份額價格抬高，讓下一筆存款被四捨五入到接近零。只有透過金庫入帳的帳面價值才算過。require(shares > 0) 會被隱藏測試打掉。漏洞類型上記錄的損失約 700 萬與約 2,000 萬美元。進階，類別 1。二十道變體。",
    "proof.kicker": "［鏈上證明］",
    "proof.h1": "三次門檻鑄造。",
    "proof.h2": "一次已揭示的傳奇。",
    "proof.lede": "三次 Muse Spark 場次鑄在 2-of-3 收藏合約上。每次三位驗證者都簽名，送出的是兩份。verify_evidence.py 為 OK。這張卡是較早那份合約上的技能 #7，來自簽章重放的鑄造。該代幣之後揭示為傳奇。",
    "proof.cap": "AxVigilSkill #7 · locked() 為真 · 最高難度傳奇 · 一次權限控制解題。",
    "proof.tx": "鑄造交易",
    "proof.copy": "複製",
    "proof.when": "區塊時間",
    "proof.col": "收藏 #2",
    "proof.skill": "技能 #7",
    "proof.reg": "Agent 註冊表",
    "proof.grade": "事件上的評分",
    "proof.gradeV": "權限控制 · 傳奇 · 池 2 · 批次 2 · Agent ID 7 · 解題總數 1",
    "proof.batch": "批次 2 揭示",
    "proof.batchV": "已揭示。代幣 #2 為傳奇，artId 320000。重算不符數：0。簽章者已輪換到一把不屬於擁有者的專用金鑰。",
    "proof.th": "門檻收藏合約",
    "proof.ths": "門檻技能合約",
    "proof.earlier": "更早的一次冒煙測試用的是參考解，不是 Muse Spark，把收藏 #1 鑄給 Agent ID 1。批次 1 已揭示為 COMMON，artId 20000。紀錄留在 deployments/bsc-testnet-97.json 的 smokeTest。",
    "trust.kicker": "［信任與可驗證性］",
    "trust.h1": "一次通過代表什麼。",
    "trust.h2": "以及它不代表什麼。",
    "trust.lede": "一次通過代表一個沙箱評分器接受了針對一道變體的一份修補。提交雜湊承諾了題目編號、種子、修補與概念驗證。第一份收藏合約的簽章者已輪換到一把不屬於擁有者的專用金鑰。門檻收藏合約的擁有者是另一個位址，而且不是驗證者。",
    "trust.eT": "證據包",
    "trust.eD": "每次評分提交都會寫下正規 JSON，加上修補、概念驗證、渲染後的原始碼與評分日誌。程序內計算本地 CIDv1（raw、sha2-256）。選擇性的 IPFS 釘選失敗，不會讓評分失敗。包裡有變體種子，雜湊才能重算。seedCommitment 是該種子八位元組大端序的 keccak。鏈上的連結是 Minted.submissionHash，不是新欄位。scripts/verify_evidence.py 可以重跑檢查。",
    "trust.tT": "2-of-3 驗證者鑄造",
    "trust.tD": "收藏合約 0x0e87…C8eB 與技能合約 0xE165…5F59 已上線。門檻是 2-of-3。三位驗證者（0xc32d…95F9、0xD5f5…4645、0x133F…ec7f）目前是許可制，由團隊運行。每位重評證據包，只有自己的評分通過才簽名。開放集合是計畫。三次 Muse Spark 鑄造用了其中兩份簽章。較早的收藏合約 0x0658…4658 仍是單一簽章者。",
    "trust.pT": "預先驗證的即時題",
    "trust.pD": "離線題庫是 120 道變體，每個漏洞類型 20 道，計入之前都做過參考檢查。即時發題也會在顯示原始碼之前檢查該種子（AXVIGIL_REFERENCE_CHECK，預設開啟），並跳過重複的結構指紋。這不是一份公開的、涵蓋未來每一顆種子的清單。",
    "trust.dT": "Docker，無網路",
    "trust.dD": "Docker 隔離已經實作：axvigil-sandbox:1.8.7、--network none、唯讀根檔案系統、uid 1000、CPU／記憶體／行程數限制，以及 tmpfs 工作目錄。包含三次門檻鑄造在內的實測評分，用的是離線子行程。那台機器沒有安裝 Docker。映像建好之前，有一項映像測試會被略過。兩種模式都不是 TEE，也不是 zkVM。",
    "trust.sT": "種子承諾揭示",
    "trust.sD": "第一份收藏合約的批次 2 已揭示。代幣 #1 為 COMMON，artId 20000。代幣 #2 為傳奇，artId 320000。重算不符數：0。三枚門檻代幣仍未揭示。這個隨機有已知的擁有者影響。Chainlink VRF 是路線圖，並沒有被寫成已經在進行的工作。",
    "trust.gT": "發現與修復",
    "trust.gD": "通過的紀錄顯示 agent 能在受控目標上修好已知類別。防禦網路還需要找出未知漏洞。熔爐沒有測這個。若之後有下一層，範圍是紀錄上已有類別內的模式初篩，而且是輔助性的。",
    "biz.kicker": "［永續］",
    "biz.h1": "沒有發行代幣。",
    "biz.h2": "這不是要約。",
    "biz.lede": "積分是鏈下分數，沒有金錢價值。收藏不付息、不能贖回，也不是對收入的請求權。專案打算靠穩定幣或法幣費用運作。代幣是更後面的設計。那些費用不需要它，它也還沒有發行。",
    "biz.aK": "階段 A · 現在",
    "biz.aT": "積分，沒有收入",
    "biz.aD": "通過的工作計分：基礎 1、進階 3、傳奇 8。這個階段沒有現金流。每個 Agent ID 兩次獎勵場次。合約另外會拒絕第三次鑄造。",
    "biz.bK": "階段 B · 計畫",
    "biz.bT": "收費，不靠代幣",
    "biz.bD": "協議為修復或懸賞付費。實驗室為私有評分回合付費。審計公司按量為預篩付費。作者在漏洞類型被使用時分成。這些都還沒有實作、沒有定價、也沒有合約。",
    "biz.cK": "階段 C · 未發行",
    "biz.cT": "效用代幣，有條件",
    "biz.cD": "只有兩件事都成立才發行：多驗證者評分已經上線，而且階段 B 有真實付費需求。預定用途：驗證者質押與罰沒、費用匯（買入銷毀或分配給驗證者）、作者與 agent 的使用獎勵，以及對漏洞類型庫與罰沒參數的治理。發行前需要法律審查。這裡沒有任何招攬。",
    "biz.ill": "示例供應量 · 可能改變 · 不是上限，也不是表決",
    "biz.illLede": "示例供應量 1,000,000,000 單位，來自白皮書的討論稿。沒有發出的部分不會鑄出。已經以代幣計價的費用，草稿是一半銷毀、一半付給已質押的驗證者。穩定幣費用留在穩定幣，除非之後的治理另有決定。那條路徑沒有建成。",
    "biz.cap": "示例分配。不是要約。",
    "biz.th1": "桶",
    "biz.th2": "比例",
    "biz.th3": "解鎖，示例",
    "biz.u": "Agent 與作者的使用獎勵",
    "biz.uD": "只依量測到的使用，在四年內發出。沒發出的不鑄造。",
    "biz.v": "驗證者激勵",
    "biz.vD": "四年，而且只給已質押的驗證者。",
    "biz.e": "生態與補助",
    "biz.eD": "12 個月懸崖，其後 36 個月按月。",
    "biz.co": "貢獻者",
    "biz.coD": "12 個月懸崖，其後 36 個月按月。",
    "biz.tr": "國庫",
    "biz.trD": "發行時鎖定。之後只由本節的治理釋出。",
    "road.kicker": "［路線圖］",
    "road.h1": "已上線，然後才是計畫。",
    "road.h2": "後面的都還沒上線。",
    "road.t0": "階段 0 · BSC 測試網",
    "road.d0": "漏洞沙盒。隱藏測試評分。2-of-3 驗證者鑄造。證據 CID。三次 Muse Spark 門檻鑄造，verify_evidence.py 為 OK。實測評分用的是子行程沙箱。",
    "road.t1": "階段 1",
    "road.d1": "用真實的 agent 註冊表換掉 MockAgentID。外部審查評分器。揭示門檻批次。讓 Docker 沙箱跑實測評分。公布多模型競技場結果。",
    "road.t2": "階段 2",
    "road.d2": "在真實協議上做掃描試點，以及賞金對接。更多漏洞家族。開放的驗證者集合。",
    "road.t3": "階段 3",
    "road.d3": "去中心化的驗證者網路。效用代幣只依白皮書永續章節所述。不是要約。主網。",
    "close.h1": "把模型指向真實的漏洞。",
    "close.h2": "然後讓它證明修復。",
    "foot.blurb": "給會修智能合約漏洞的 AI agent 的試煉場。Meta Global AI Developer Hackathon。BSC 測試網。僅沙箱。",
    "foot.project": "專案",
    "nav.pitch": "簡報",
    "foot.pitch": "簡報",
    "foot.board": "排行榜",
    "foot.docs": "白皮書",
    "foot.en": "英文",
    "foot.zh": "繁體中文",
    "foot.pitchMd": "簡報筆記",
    "foot.chain": "鏈 97",
    "foot.col": "收藏",
    "foot.skill": "技能紀錄",
    "foot.mint": "鑄造 #2",
    "foot.disc": "僅沙箱與測試網。未經審計。不要用於生產資金。沒有發行代幣，本頁也不是出售代幣的要約。技能紀錄不能購買或轉移。能力紀錄不是「agent 能找出未知漏洞」的主張。"
  };

  document.querySelectorAll("[data-i18n]").forEach(function (el) {
    el.dataset.en = el.textContent;
  });
  document.querySelectorAll("[data-i18n-aria]").forEach(function (el) {
    el.dataset.enAria = el.getAttribute("aria-label") || "";
  });

  var lang = "en";
  try {
    var saved = localStorage.getItem("axvigil-lang") || localStorage.getItem("axv_lang") || sessionStorage.getItem("axv-lang");
    if (saved === "zh-TW" || saved === "en") lang = saved;
  } catch (err) { /* ignore */ }

  function apply(next) {
    lang = next;
    document.documentElement.lang = next === "zh-TW" ? "zh-Hant" : "en";
    var heroPack = facts.heroCopy && facts.heroCopy[next === "zh-TW" ? "zh-TW" : "en"];
    document.querySelectorAll("[data-i18n]").forEach(function (el) {
      var key = el.getAttribute("data-i18n");
      if (heroPack && key.indexOf("hero.") === 0 && Object.prototype.hasOwnProperty.call(heroPack, key.slice(5))) {
        el.textContent = heroPack[key.slice(5)];
        return;
      }
      el.textContent = next === "zh-TW" && Object.prototype.hasOwnProperty.call(ZH, key) ? ZH[key] : el.dataset.en;
    });
    document.querySelectorAll("[data-i18n-aria]").forEach(function (el) {
      var key = el.getAttribute("data-i18n-aria");
      var label = next === "zh-TW" && ZH[key] ? ZH[key] : el.dataset.enAria;
      el.setAttribute("aria-label", label);
    });
    document.querySelectorAll(".lang button").forEach(function (button) {
      button.setAttribute("aria-pressed", String(button.getAttribute("data-lang") === next));
    });
    bindFacts(next);
    document.querySelectorAll("[data-leaderboard]").forEach(function (el) {
      el.hidden = facts.leaderboardLive !== true;
    });
    document.querySelectorAll("table").forEach(function (table) {
      var heads = Array.prototype.map.call(table.querySelectorAll("thead th"), function (th) {
        return th.textContent.trim();
      });
      table.querySelectorAll("tbody tr").forEach(function (row) {
        Array.prototype.forEach.call(row.children, function (cell, index) {
          if (heads[index]) cell.setAttribute("data-label", heads[index]);
        });
      });
    });
    try {
      localStorage.setItem("axvigil-lang", next);
      localStorage.setItem("axv_lang", next);
      sessionStorage.setItem("axv-lang", next);
    } catch (err) { /* ignore */ }
    document.dispatchEvent(new CustomEvent("axv:lang"));
  }

  document.querySelectorAll(".lang button").forEach(function (button) {
    button.addEventListener("click", function () { apply(button.getAttribute("data-lang")); });
  });
  apply(lang);

  var toggle = document.querySelector(".nav-toggle");
  var nav = document.getElementById("site-nav");
  if (toggle && nav) {
    toggle.addEventListener("click", function () {
      var open = toggle.getAttribute("aria-expanded") === "true";
      toggle.setAttribute("aria-expanded", String(!open));
      nav.classList.toggle("open", !open);
    });
    nav.querySelectorAll("a").forEach(function (link) {
      link.addEventListener("click", function () {
        toggle.setAttribute("aria-expanded", "false");
        nav.classList.remove("open");
      });
    });
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") {
        toggle.setAttribute("aria-expanded", "false");
        nav.classList.remove("open");
      }
    });
  }

  var sectionLinks = Array.prototype.filter.call(document.querySelectorAll(".nav-links a"), function (a) {
    return a.getAttribute("href").charAt(0) === "#";
  });
  if ("IntersectionObserver" in window) {
    var spy = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        sectionLinks.forEach(function (a) { a.removeAttribute("aria-current"); });
        var match = sectionLinks.filter(function (a) { return a.getAttribute("href") === "#" + entry.target.id; })[0];
        if (match) match.setAttribute("aria-current", "true");
      });
    }, { rootMargin: "-45% 0px -45% 0px", threshold: 0.01 });
    sectionLinks.forEach(function (a) {
      var node = document.querySelector(a.getAttribute("href"));
      if (node) spy.observe(node);
    });
  }

  document.querySelectorAll(".acc-btn").forEach(function (button) {
    button.addEventListener("click", function () {
      var panel = document.getElementById(button.getAttribute("aria-controls"));
      var open = button.getAttribute("aria-expanded") === "true";
      button.setAttribute("aria-expanded", String(!open));
      if (panel) panel.hidden = open;
    });
  });

  var tabs = Array.prototype.slice.call(document.querySelectorAll("[role='tab']"));
  function selectTab(tab) {
    tabs.forEach(function (item) {
      var on = item === tab;
      item.setAttribute("aria-selected", String(on));
      item.tabIndex = on ? 0 : -1;
      var panel = document.getElementById(item.getAttribute("aria-controls"));
      if (panel) panel.hidden = !on;
    });
  }
  tabs.forEach(function (tab, index) {
    tab.addEventListener("click", function () { selectTab(tab); });
    tab.addEventListener("keydown", function (event) {
      var next = index;
      if (event.key === "ArrowRight") next = (index + 1) % tabs.length;
      else if (event.key === "ArrowLeft") next = (index - 1 + tabs.length) % tabs.length;
      else return;
      event.preventDefault();
      tabs[next].focus();
      selectTab(tabs[next]);
    });
  });

  var live = document.getElementById("copied");
  document.querySelectorAll(".copy").forEach(function (button) {
    button.addEventListener("click", function () {
      var value = String(get(button.getAttribute("data-copy")) || "");
      var done = lang === "zh-TW" ? "已複製。" : "Copied.";
      var fail = lang === "zh-TW" ? "無法複製。" : "Could not copy.";
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(value).then(function () {
          if (live) live.textContent = done;
        }).catch(function () {
          if (live) live.textContent = fail;
        });
      } else if (live) {
        live.textContent = fail;
      }
    });
  });

})();
