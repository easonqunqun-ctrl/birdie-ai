// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Chinese (`zh`).
class AppLocalizationsZh extends AppLocalizations {
  AppLocalizationsZh([String locale = 'zh']) : super(locale);

  @override
  String get appName => '领翼golf';

  @override
  String get appNameShort => '领翼';

  @override
  String get appNameAccent => 'golf';

  @override
  String get tagline => '你的随身高尔夫智能教练';

  @override
  String get language => '语言';

  @override
  String get languageSystem => '跟随系统';

  @override
  String get languageZh => '简体中文';

  @override
  String get languageEn => 'English';

  @override
  String get tabHome => '首页';

  @override
  String get tabCoach => 'AI 教练';

  @override
  String get tabTraining => '训练';

  @override
  String get tabProfile => '我的';

  @override
  String get login => '登录';

  @override
  String get goLogin => '去登录';

  @override
  String get loginRequiredHint => '挥杆分析与 AI 对话需登录后使用。';

  @override
  String get agreeFirst => '请先勾选协议';

  @override
  String get agreeReadPrefix => '我已阅读并同意';

  @override
  String get userAgreement => '《用户服务协议》';

  @override
  String get privacyPolicy => '《隐私政策》';

  @override
  String get andWord => '和';

  @override
  String get browseAsGuest => '暂不登录，先逛逛';

  @override
  String get signingIn => '登录中...';

  @override
  String get wechatLogin => '微信一键登录';

  @override
  String get appleLoginHint => '本版本请使用「通过 Apple 登录」，无需安装微信';

  @override
  String get appleDeviceRequired => '请使用支持 Sign in with Apple 的设备登录';

  @override
  String get inviteOptional => '有邀请码？点击填写（可选）';

  @override
  String get inviteHint => '请输入 8 位邀请码';

  @override
  String get inviteBonus => '使用邀请码：你与邀请人本月各 +1 次分析';

  @override
  String get featureSwing => 'AI 挥杆分析，30 秒出报告';

  @override
  String get featureCoach => '24 小时 AI 教练在线问答';

  @override
  String get featurePlan => '个性化训练方案';

  @override
  String get welcomeUse => '欢迎使用';

  @override
  String get guestSubtitle1 => '可先了解产品与功能';

  @override
  String get guestSubtitle2 => '再选择是否登录';

  @override
  String get guestLegalHint => '挥杆分析与 AI 对话需登录后使用。下方可查看示例报告与协议。';

  @override
  String get loginToAnalyze => '登录后开始分析';

  @override
  String get productOffers => '本产品提供';

  @override
  String get guestFeatSwing => 'AI 挥杆分析，短视频出报告';

  @override
  String get guestFeatCoach => 'AI 教练在线答疑（生成式内容，仅供参考）';

  @override
  String get guestFeatPlan => '基于分析的训练计划与打卡';

  @override
  String get sampleReportTitle => '先看一份示例报告';

  @override
  String get sampleReportSubGuest => '无需登录 · 不消耗次数';

  @override
  String get sampleReportSubUser => '了解 AI 能给你什么 · 不消耗次数';

  @override
  String get coachIntroTitle => 'AI 教练 · 了解能力';

  @override
  String get coachIntroSub => '进入页内说明，对话前需登录';

  @override
  String helloGolfer(String name) {
    return '你好，$name 👋';
  }

  @override
  String get golferFallback => '球友';

  @override
  String get heroCta => '拍一段挥杆，30 秒拿到 AI 专属报告';

  @override
  String get uploadNewSwing => '+ 上传新挥杆';

  @override
  String get startFirstAnalysis => '🎬 开始第一次分析';

  @override
  String get quotaMemberUnlimited => '会员 · 挥杆分析无限次';

  @override
  String quotaMonthRemaining(int remaining, int total) {
    return '本月剩余分析 $remaining/$total 次';
  }

  @override
  String get statTotalAnalyses => '累计分析';

  @override
  String get statBestScore => '最佳得分';

  @override
  String get statStreak => '连续天数';

  @override
  String get askCoach => '问 AI 教练';

  @override
  String get memberUnlimited => '会员无限次';

  @override
  String chatRemainingToday(int n) {
    return '今日剩余 $n 次';
  }

  @override
  String get recentAnalyses => '最近分析';

  @override
  String get viewAll => '查看全部 ›';

  @override
  String get noAnalysesYet => '还没有分析记录，上传第一段挥杆吧';

  @override
  String get statusFailed => '失败';

  @override
  String get statusAnalyzing => '分析中';

  @override
  String get quotaExhaustedTitle => '本月分析次数已用完';

  @override
  String get quotaExhaustedBody => '本月免费分析次数已用完。请下月额度刷新后再试，或等待后续 App 内购买会员上线。';

  @override
  String get gotIt => '我知道了';

  @override
  String get viewBenefits => '查看权益说明';

  @override
  String todayAt(String time) {
    return '今天 $time';
  }

  @override
  String get scoreUnit => ' 分';

  @override
  String get latestShot => '最近一杆';

  @override
  String get analysisDone => '已完成分析';

  @override
  String get settings => '设置';

  @override
  String get sectionExperience => '体验';

  @override
  String get replayCaptureGuide => '重新查看拍摄指南';

  @override
  String get guideResetToast => '已重置，下次分析会再次显示拍摄指南';

  @override
  String get clearCache => '清除本地缓存';

  @override
  String get clearCacheBody => '将清除本地登录态与设置缓存，需要重新登录。确认继续？';

  @override
  String get cancel => '取消';

  @override
  String get confirmClear => '清除';

  @override
  String get sectionLegal => '法律与协议';

  @override
  String get aboutApp => '关于领翼golf';

  @override
  String get deleteAccount => '注销账号';

  @override
  String get logout => '退出登录';

  @override
  String get logoutConfirm => '确认退出登录？';

  @override
  String get prompt => '提示';

  @override
  String get membershipCenter => '会员中心';

  @override
  String get freeUser => '免费用户';

  @override
  String get memberThanks => '感谢支持，尽情享受全部会员权益';

  @override
  String get membershipFreeHint => '本版本 App 提供免费额度；会员购买能力将通过苹果 App 内购买提供';

  @override
  String get membershipNoIap =>
      '当前版本暂不在 App 内开通付费会员。请继续使用免费分析与对话额度；后续若提供会员订阅，将仅通过苹果 App 内购买完成。';

  @override
  String get memberYearly => '年度会员';

  @override
  String get memberMonthly => '月度会员';

  @override
  String get memberGeneric => '会员';

  @override
  String memberRemainingDays(String label, int days) {
    return '$label · 还剩 $days 天';
  }

  @override
  String get benefitSwing => '挥杆视频分析';

  @override
  String get benefitCoach => 'AI 教练对话';

  @override
  String get benefitPlan => '本周训练计划';

  @override
  String get benefitCurve => '进步曲线';

  @override
  String get benefitCompare => '历史报告对比';

  @override
  String get tierLimitedMonth => '每月有限次数';

  @override
  String get tierLimitedDay => '每日有限次数';

  @override
  String get tierViewOnly => '仅查看';

  @override
  String get tierBasic => '基础';

  @override
  String get tierUnlimited => '无限次';

  @override
  String get tierFullPlan => '完整个性化';

  @override
  String get tierFullHistory => '完整历史与折线';

  @override
  String get tierSideBySide => '并排对比';

  @override
  String get helpCenter => '帮助中心';

  @override
  String get faqShootQ => '如何拍摄一段合格的挥杆视频？';

  @override
  String get faqShootA =>
      '建议在光线充足的场地，手机横屏或竖屏固定，完整拍下从预备到收杆的动作；正面（Face-On）或侧面（Down-the-Line）机位皆可，时长 2-30 秒。';

  @override
  String get faqHowLongQ => '分析需要多久？';

  @override
  String get faqHowLongA => '视频上传后，AI 通常在 30 秒内完成分析并生成报告，弱网时可能稍长。';

  @override
  String get faqQuotaQ => '分析次数用完了怎么办？';

  @override
  String get faqQuotaA => '免费额度每月刷新。本版本 App 内暂不提供付费会员购买；后续若开通将通过苹果 App 内购买。';

  @override
  String get faqCoachQ => 'AI 教练能回答哪些问题？';

  @override
  String get faqCoachA => '挥杆技术、训练计划、规则疑问、装备选择等高尔夫相关问题都可以问。';

  @override
  String get faqDataQ => '我的数据安全吗？';

  @override
  String get faqDataA =>
      '挥杆视频与账号数据由本公司云端处理；对话类生成可能经国内大模型（如 DeepSeek）。你可随时在「我的」删除或注销账号。';

  @override
  String get aiConsentTitle => 'AI 数据处理说明';

  @override
  String get aiConsentSwing => '将上传你选择的挥杆视频及相关参数（球杆、机位等），用于生成分析报告。';

  @override
  String get aiConsentChat => '将发送你输入的对话文本及必要上下文，用于生成 AI 教练回复。';

  @override
  String get aiConsentReceivers => '接收方：';

  @override
  String get aiConsentOurCloud => '领翼golf 云端服务（北京思无界控股有限公司）';

  @override
  String get aiConsentProvider => 'DeepSeek（深度求索）等大模型服务商（处理对话/文案类生成时）';

  @override
  String get aiConsentPurpose =>
      '用途：仅为你提供本产品的挥杆分析或 AI 答疑，不会出售你的个人信息。在你未另行单独同意前，不会将可识别你身份的内容用于无关模型训练。\n\n详情见《隐私政策》。是否同意继续？';

  @override
  String get disagree => '不同意';

  @override
  String get agreeContinue => '同意并继续';

  @override
  String get coachWelcome => '你好！我是领翼golf 的 AI 高尔夫教练。随时问我挥杆技术、练习方法或高尔夫知识方面的问题。';

  @override
  String get chatQuotaExhausted => '今日对话次数已用完';

  @override
  String get rateLimited => '操作太快了，稍等片刻再试';

  @override
  String get clearChatTitle => '清空对话？';

  @override
  String get clearChatStreaming => '当前 AI 正在回复，点击清空会立即中断。';

  @override
  String get clearChatBody => '会删除本次会话的全部历史，AI 将以新会话身份开始。';

  @override
  String get clearAction => '清空';

  @override
  String get loginToChat => '登录后与 AI 教练对话';

  @override
  String get connectingCoach => '正在接入 AI 教练...';

  @override
  String get loadFailed => '加载失败';

  @override
  String get reload => '重新加载';

  @override
  String get reportBasedChat => '基于报告的对话';

  @override
  String get viewOriginalReport => '查看原报告 ›';

  @override
  String get tryThese => '试试这些问题：';

  @override
  String get needsAnalysis => '需分析';

  @override
  String get needUploadFirstTitle => '需要先上传一次挥杆';

  @override
  String get needUploadFirstBody => '这个问题需要结合你的挥杆分析，先去「首页 → 开始分析」拍一次吧。';

  @override
  String get copied => '已复制';

  @override
  String get chatUsedUp => '今日已用完';

  @override
  String chatRemainFrac(int remaining, int total) {
    return '今日剩余 $remaining/$total 次';
  }

  @override
  String get chatUsedUpHint => '今日对话已用完';

  @override
  String get aiReplying => 'AI 正在回复，稍等片刻...';

  @override
  String get askCoachHint => '问问 AI 教练...';

  @override
  String get me => '我';

  @override
  String get tapRetry => '↻ 点击重试';

  @override
  String get training => '训练';

  @override
  String get loginToSeePlan => '登录后查看训练计划';

  @override
  String get loginToSeeCalendar => '打卡日历与进步曲线也会在登录后展示';

  @override
  String get checkinFailed => '打卡失败，请稍后重试';

  @override
  String get checkinOk => '打卡成功！';

  @override
  String checkinStreak(int n) {
    return '打卡成功！连续 $n 天';
  }

  @override
  String get checkinSuggestReshoot => '建议用相同机位再拍一次挥杆，对比是否改善。';

  @override
  String get later => '稍后再说';

  @override
  String get goCapture => '去拍摄';

  @override
  String get practiceCalendar => '练习日历';

  @override
  String get progressCurve => '进步曲线';

  @override
  String get last90 => '近 90 天';

  @override
  String get allTime => '全部';

  @override
  String get progressHint => '完成分析后可查看得分趋势；会员可见更完整曲线。';

  @override
  String get noPlanTitle => '还没有训练计划';

  @override
  String get noPlanBody => '先上传一次挥杆视频，AI 会根据分析结果为你生成本周专属训练';

  @override
  String get goUpload => '去上传视频';

  @override
  String taskCount(int n) {
    return '$n 个任务';
  }

  @override
  String get loadFailedRetry => '加载失败，请稍后再试';

  @override
  String get weekPlan => '本周训练';

  @override
  String get completed => '已完成';

  @override
  String get pending => '待完成';

  @override
  String streakDays(int n) {
    return '连续打卡 $n 天';
  }

  @override
  String get submitting => '提交中…';

  @override
  String get completeCheckin => '完成打卡';

  @override
  String get profileSyncHint => '登录后同步个人资料与分析记录';

  @override
  String get myReports => '我的分析报告';

  @override
  String get coachChat => 'AI 教练对话';

  @override
  String get myClubs => '我的装备';

  @override
  String get lessons => '课程学习';

  @override
  String get proLibrary => '球手对比库';

  @override
  String get meetup => '约球邀请';

  @override
  String get deletionPending => '账号已排期注销，点此查看或撤销';

  @override
  String get edit => '编辑';

  @override
  String get golfProfile => '高尔夫档案';

  @override
  String get modify => '修改';

  @override
  String get level => '水平';

  @override
  String get goals => '目标';

  @override
  String get practiceFreq => '练习频率';

  @override
  String get notSet => '未设置';

  @override
  String get statAnalyses => '分析次数';

  @override
  String get statCheckin => '连续打卡';

  @override
  String get statHighScore => '最高分';

  @override
  String get consentWelcome => '欢迎使用领翼golf';

  @override
  String get consentBefore => '在开始之前';

  @override
  String get consentIntro => '我们非常重视你的个人信息保护。使用本产品，我们需要收集：';

  @override
  String get consentBulletApple => 'Apple 账号标识：用于 Sign in with Apple 登录与账号识别。';

  @override
  String get consentBulletVideo =>
      '挥杆视频：仅在你主动拍摄/选择并同意后上传，用于 AI 分析并生成报告（本公司云端）。';

  @override
  String get consentBulletChat => '对话内容：用于 AI 教练问答；经你同意后通过大模型（如 DeepSeek）生成回复。';

  @override
  String get consentStorage => '数据由本公司云端处理；对话类可能经国内大模型。你可在「我的」随时查看、删除或注销账号。';

  @override
  String get consentDisagreeExit => '若暂不同意，请退出。你可以随时重新进入并选择同意。';

  @override
  String get notNow => '暂不同意';

  @override
  String get disagreeCannotUse => '不同意将无法使用本产品';

  @override
  String get withWord => '与';

  @override
  String get colBenefit => '权益';

  @override
  String get colFree => '免费';

  @override
  String get listSep => '、';

  @override
  String get weekdayMon => '一';

  @override
  String get weekdayTue => '二';

  @override
  String get weekdayWed => '三';

  @override
  String get weekdayThu => '四';

  @override
  String get weekdayFri => '五';

  @override
  String get weekdaySat => '六';

  @override
  String get weekdaySun => '日';

  @override
  String dateWeekday(String md, String wd) {
    return '$md 周$wd';
  }

  @override
  String get levelBeginner => '初学者';

  @override
  String get levelElementary => '初级';

  @override
  String get levelIntermediate => '中级';

  @override
  String get levelAdvanced => '高级';

  @override
  String get goalDistance => '提升距离';

  @override
  String get goalAccuracy => '提升准度';

  @override
  String get goalShortGame => '短杆球技';

  @override
  String get goalPutting => '推杆技术';

  @override
  String get goalConsistency => '一致性';

  @override
  String get freqOccasional => '偶尔';

  @override
  String get freqOnce => '每周 1 次';

  @override
  String get freqFrequent => '每周 2-3 次';

  @override
  String get freqDaily => '几乎每天';

  @override
  String get captureTitle => '挥杆分析';

  @override
  String get captureOnlyMp4Mov => '仅支持 mp4 / mov 视频';

  @override
  String get captureTooLarge => '视频不能超过 100MB';

  @override
  String captureTooShort(int n) {
    return '视频太短（需 ≥ ${n}s）';
  }

  @override
  String captureTooLong(int n) {
    return '视频太长（需 ≤ ${n}s）';
  }

  @override
  String capturePickFailed(String error) {
    return '选取视频失败：$error';
  }

  @override
  String get captureNeedVideo => '请先拍摄或选择挥杆视频';

  @override
  String captureLimits(int min, int max, int mb, String ext) {
    return '时长 $min-$max s · 大小 ≤ ${mb}MB · 支持 $ext';
  }

  @override
  String get captureNextParams => '下一步：选择参数';

  @override
  String get captureTrySample => '先用示例视频体验一下';

  @override
  String get captureCenterSubject => '对准人物 · 居中入画';

  @override
  String get captureTipFraming => '将球员放在画面中央，脚到头部全部露出';

  @override
  String get captureTipLength => '拍满至少 2 秒（建议 3–5 秒），只录 1 次完整挥杆';

  @override
  String get captureTipLight => '优选自然光，避免强背光和严重抖动';

  @override
  String get capturePrompt => '拍摄或选择一段挥杆视频（2-30 秒）';

  @override
  String captureSelected(String duration, String size) {
    return '已选择 · ${duration}s · ${size}MB';
  }

  @override
  String get record => '录制';

  @override
  String get album => '相册';

  @override
  String get paramsTitle => '分析参数';

  @override
  String get paramsMode => '分析模式';

  @override
  String get paramsModeHint => '推杆/切杆需服务端灰度开启；若创建失败请改回全挥杆。';

  @override
  String get paramsClub => '球杆';

  @override
  String get paramsCamera => '拍摄机位';

  @override
  String get paramsUploading => '上传中…';

  @override
  String get paramsDetecting => '识别挥杆段…';

  @override
  String get paramsCreating => '创建分析任务…';

  @override
  String get paramsStartFailed => '发起分析失败';

  @override
  String get paramsProcessing => '处理中…';

  @override
  String get paramsStart => '开始分析';

  @override
  String get modeFullSwing => '全挥杆';

  @override
  String get modeFullSwingSub => '铁木杆 / 一号木';

  @override
  String get modePutting => '推杆';

  @override
  String get modePuttingSub => '果岭推杆';

  @override
  String get modeChipping => '切杆';

  @override
  String get modeChippingSub => '短切 / 劈起';

  @override
  String get waitingReceived => '视频已接收';

  @override
  String get waitingPose => '识别人体姿态';

  @override
  String get waitingSwing => '分析挥杆动作';

  @override
  String get waitingDiagnose => '生成诊断建议';

  @override
  String get waitingRender => '渲染分析报告';

  @override
  String get waitingDone => '分析完成';

  @override
  String get waitingInProgress => 'AI 正在分析你的挥杆';

  @override
  String get waitingOpening => '即将为你打开报告…';

  @override
  String waitingEtaSeconds(int n) {
    return '预计还需 $n 秒';
  }

  @override
  String get waitingEtaSoon => '预计还需不到 30 秒';

  @override
  String get waitingSlowHint => '分析可能比预期稍久，请耐心等待；仍可留在本页或稍后在「我的分析报告」查看结果。';

  @override
  String get waitingSlowTitle => '⏳ 分析时间比预期长';

  @override
  String get waitingSlowBody =>
      '别担心，任务还在后台跑。完成后你可以在「我的分析报告」里查看结果。你也可以先去首页做点别的。';

  @override
  String get waitingBackHome => '先回首页';

  @override
  String waitingDidYouKnow(String category) {
    return '$category  ·  你知道吗？';
  }

  @override
  String get waitingFailed => '分析失败';

  @override
  String get waitingReshoot => '重新拍摄';

  @override
  String get waitingGoHome => '去首页';

  @override
  String get reportLoading => '加载报告中…';

  @override
  String get reportLoadFailed => '报告加载失败';

  @override
  String get retry => '重试';

  @override
  String get scoreGuideLink => '分数说明 ›';

  @override
  String get sampleReportBanner => '这是演示报告，用真实数据展示 AI 能发现的问题；不消耗你的分析次数。';

  @override
  String get clipOriginal => '原片';

  @override
  String get clipSkeleton => '骨骼';

  @override
  String get playbackSpeed => '倍速';

  @override
  String get vsLastSameType => '较最近一次同类型';

  @override
  String get highlightsThisSwing => '本次亮点';

  @override
  String get filmingTips => '拍摄提示';

  @override
  String get sixDimScores => '六维评分';

  @override
  String get tapPhaseToJump => '点击阶段跳到对应画面';

  @override
  String get mostNeedImprove => '最需改进';

  @override
  String get otherIssues => '其他问题';

  @override
  String get issueDiagnosis => '问题诊断';

  @override
  String get weeklyFocus => '本周主攻';

  @override
  String recommendedDrill(String name) {
    return '推荐练习：$name';
  }

  @override
  String get goPracticeThis => '去练这个动作';

  @override
  String get askCoachBtn => '问 AI 教练';

  @override
  String get proCompare => '职业对比';

  @override
  String get scorePoster => '成绩海报';

  @override
  String get share => '分享';

  @override
  String get shootAgain => '再拍一段';

  @override
  String get backHome => '返回首页';

  @override
  String get skipProfileTitle => '跳过档案？';

  @override
  String get skipProfileBody => '你可以在「我的」里随时补填，AI 教练会更懂你。';

  @override
  String get keepFilling => '继续填写';

  @override
  String get confirmSkip => '确认跳过';

  @override
  String get skipping => '跳过中…';

  @override
  String get skip => '跳过';

  @override
  String get onboardingLevelQ => '你的高尔夫水平？';

  @override
  String onboardingGoalsQ(int n) {
    return '主要目标？（最多 $n 个）';
  }

  @override
  String get onboardingFreqQ => '练习频率？';

  @override
  String get previousStep => '上一步';

  @override
  String get nextStep => '下一步';

  @override
  String get done => '完成';

  @override
  String monthCheckins(int n) {
    return '本月打卡 $n 次';
  }

  @override
  String get levelBeginnerDesc => '刚接触不到 1 年';

  @override
  String get levelElementaryDesc => '1-3 年，差点 25+';

  @override
  String get levelIntermediateDesc => '差点 10-25';

  @override
  String get levelAdvancedDesc => '差点 10 以下';
}
