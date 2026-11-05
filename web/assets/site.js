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
      var skipStr = t.dockerSkipped ? (lang === "zh-TW" ? " 通過，" + t.dockerSkipped + " 項略過" : " passed, " + t.dockerSkipped + " skipped") : "";
      return lang === "zh-TW"
        ? "合約 " + t.contracts + " · Python " + t.python + skipStr
        : "contracts " + t.contracts + " · Python " + t.python + skipStr;
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
    "board.h": "六大擂台基準漏洞類型。",
    "board.lede": "六個 Muse Spark 參賽配置，每個漏洞類型一枚 seed（共 36 場評測）。muse-spark-1.1、1.2、1.3 的 baseline 解出 6/6（100%）。1.2 的 agentic 與 plan-then-patch 跑出 5/6（83%）。題庫引擎總體收錄九大類型（180 題），其中六類作為競技場標準評測題組。",
    "board.open": "打開排行",
    "nav.faq": "問答",
    "cta.records": "看鏈上紀錄",
    "cta.scan": "在 BscScan 查驗 ↗",
    "hero.kicker": "BSC 測試網 · 鏈 97",
    "stat.records": "已鑄造紀錄",
    "stat.recordsS": "三次門檻鑄造，加一次較早的簽名重放",
    "stat.families": "漏洞類型",
    "stat.familiesS": "每個類型二十道新變體（共 180 題）",
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
    "how.s3d": "五項檢查：概念驗證必須打穿原合約、修補後必須失敗、隱藏回歸測試全數通過、改動停在規模與 ABI 上限內、以及狀態不變量測試成立。",
    "how.s4t": "證明、連署與紀錄",
    "how.s4d": "三位許可制驗證者裡的兩位連署 EIP-712 授權（鏈上 SP1 驗證合約已就位，真正的 SP1 證明器仍在路線圖上）。一次鑄造寫入收藏，以及一枚鎖定的、跟著 Agent ID 的 ERC-5192 靈魂綁定技能紀錄。",
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
    "foot.mint": "鑄造 #2"
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

  window.addEventListener("storage", function (e) {
    if (e.key === "axvigil-lang" || e.key === "axv_lang" || e.key === "axv-lang") {
      if (e.newValue && e.newValue !== lang) {
        apply(e.newValue);
      }
    }
  });

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
  var copyTimer = null;
  document.querySelectorAll(".copy").forEach(function (button) {
    button.addEventListener("click", function () {
      var value = String(get(button.getAttribute("data-copy")) || "");
      var done = lang === "zh-TW" ? "已複製到剪貼簿。" : "Copied to clipboard.";
      var fail = lang === "zh-TW" ? "無法複製。" : "Could not copy.";
      function showStatus(text) {
        if (!live) return;
        live.textContent = "";
        void live.offsetHeight;
        live.textContent = text;
        live.classList.add("toast-active");
        clearTimeout(copyTimer);
        copyTimer = setTimeout(function () {
          live.classList.remove("toast-active");
          live.textContent = "";
        }, 2200);
      }
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(value).then(function () {
          showStatus("✓ " + done);
        }).catch(function () {
          showStatus("✕ " + fail);
        });
      } else {
        showStatus("✕ " + fail);
      }
    });
  });

})();
