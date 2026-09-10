import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:intl/intl.dart' as intl;

import 'app_localizations_en.dart';
import 'app_localizations_zh.dart';

// ignore_for_file: type=lint

/// Callers can lookup localized strings with an instance of AppLocalizations
/// returned by `AppLocalizations.of(context)`.
///
/// Applications need to include `AppLocalizations.delegate()` in their app's
/// `localizationDelegates` list, and the locales they support in the app's
/// `supportedLocales` list. For example:
///
/// ```dart
/// import 'l10n/app_localizations.dart';
///
/// return MaterialApp(
///   localizationsDelegates: AppLocalizations.localizationsDelegates,
///   supportedLocales: AppLocalizations.supportedLocales,
///   home: MyApplicationHome(),
/// );
/// ```
///
/// ## Update pubspec.yaml
///
/// Please make sure to update your pubspec.yaml to include the following
/// packages:
///
/// ```yaml
/// dependencies:
///   # Internationalization support.
///   flutter_localizations:
///     sdk: flutter
///   intl: any # Use the pinned version from flutter_localizations
///
///   # Rest of dependencies
/// ```
///
/// ## iOS Applications
///
/// iOS applications define key application metadata, including supported
/// locales, in an Info.plist file that is built into the application bundle.
/// To configure the locales supported by your app, you’ll need to edit this
/// file.
///
/// First, open your project’s ios/Runner.xcworkspace Xcode workspace file.
/// Then, in the Project Navigator, open the Info.plist file under the Runner
/// project’s Runner folder.
///
/// Next, select the Information Property List item, select Add Item from the
/// Editor menu, then select Localizations from the pop-up menu.
///
/// Select and expand the newly-created Localizations item then, for each
/// locale your application supports, add a new item and select the locale
/// you wish to add from the pop-up menu in the Value field. This list should
/// be consistent with the languages listed in the AppLocalizations.supportedLocales
/// property.
abstract class AppLocalizations {
  AppLocalizations(String locale)
    : localeName = intl.Intl.canonicalizedLocale(locale.toString());

  final String localeName;

  static AppLocalizations of(BuildContext context) {
    return Localizations.of<AppLocalizations>(context, AppLocalizations)!;
  }

  static const LocalizationsDelegate<AppLocalizations> delegate =
      _AppLocalizationsDelegate();

  /// A list of this localizations delegate along with the default localizations
  /// delegates.
  ///
  /// Returns a list of localizations delegates containing this delegate along with
  /// GlobalMaterialLocalizations.delegate, GlobalCupertinoLocalizations.delegate,
  /// and GlobalWidgetsLocalizations.delegate.
  ///
  /// Additional delegates can be added by appending to this list in
  /// MaterialApp. This list does not have to be used at all if a custom list
  /// of delegates is preferred or required.
  static const List<LocalizationsDelegate<dynamic>> localizationsDelegates =
      <LocalizationsDelegate<dynamic>>[
        delegate,
        GlobalMaterialLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
      ];

  /// A list of this localizations delegate's supported locales.
  static const List<Locale> supportedLocales = <Locale>[
    Locale('zh'),
    Locale('en'),
  ];

  /// No description provided for @appName.
  ///
  /// In zh, this message translates to:
  /// **'领翼golf'**
  String get appName;

  /// No description provided for @appNameShort.
  ///
  /// In zh, this message translates to:
  /// **'领翼'**
  String get appNameShort;

  /// No description provided for @tagline.
  ///
  /// In zh, this message translates to:
  /// **'你的随身高尔夫智能教练'**
  String get tagline;

  /// No description provided for @language.
  ///
  /// In zh, this message translates to:
  /// **'语言'**
  String get language;

  /// No description provided for @languageSystem.
  ///
  /// In zh, this message translates to:
  /// **'跟随系统'**
  String get languageSystem;

  /// No description provided for @languageZh.
  ///
  /// In zh, this message translates to:
  /// **'简体中文'**
  String get languageZh;

  /// No description provided for @languageEn.
  ///
  /// In zh, this message translates to:
  /// **'English'**
  String get languageEn;

  /// No description provided for @tabHome.
  ///
  /// In zh, this message translates to:
  /// **'首页'**
  String get tabHome;

  /// No description provided for @tabCoach.
  ///
  /// In zh, this message translates to:
  /// **'AI 教练'**
  String get tabCoach;

  /// No description provided for @tabTraining.
  ///
  /// In zh, this message translates to:
  /// **'训练'**
  String get tabTraining;

  /// No description provided for @tabProfile.
  ///
  /// In zh, this message translates to:
  /// **'我的'**
  String get tabProfile;

  /// No description provided for @login.
  ///
  /// In zh, this message translates to:
  /// **'登录'**
  String get login;

  /// No description provided for @goLogin.
  ///
  /// In zh, this message translates to:
  /// **'去登录'**
  String get goLogin;

  /// No description provided for @loginRequiredHint.
  ///
  /// In zh, this message translates to:
  /// **'挥杆分析与 AI 对话需登录后使用。'**
  String get loginRequiredHint;

  /// No description provided for @agreeFirst.
  ///
  /// In zh, this message translates to:
  /// **'请先勾选协议'**
  String get agreeFirst;

  /// No description provided for @agreeReadPrefix.
  ///
  /// In zh, this message translates to:
  /// **'我已阅读并同意'**
  String get agreeReadPrefix;

  /// No description provided for @userAgreement.
  ///
  /// In zh, this message translates to:
  /// **'《用户服务协议》'**
  String get userAgreement;

  /// No description provided for @privacyPolicy.
  ///
  /// In zh, this message translates to:
  /// **'《隐私政策》'**
  String get privacyPolicy;

  /// No description provided for @andWord.
  ///
  /// In zh, this message translates to:
  /// **'和'**
  String get andWord;

  /// No description provided for @browseAsGuest.
  ///
  /// In zh, this message translates to:
  /// **'暂不登录，先逛逛'**
  String get browseAsGuest;

  /// No description provided for @signingIn.
  ///
  /// In zh, this message translates to:
  /// **'登录中...'**
  String get signingIn;

  /// No description provided for @wechatLogin.
  ///
  /// In zh, this message translates to:
  /// **'微信一键登录'**
  String get wechatLogin;

  /// No description provided for @appleLoginHint.
  ///
  /// In zh, this message translates to:
  /// **'本版本请使用「通过 Apple 登录」，无需安装微信'**
  String get appleLoginHint;

  /// No description provided for @appleDeviceRequired.
  ///
  /// In zh, this message translates to:
  /// **'请使用支持 Sign in with Apple 的设备登录'**
  String get appleDeviceRequired;

  /// No description provided for @inviteOptional.
  ///
  /// In zh, this message translates to:
  /// **'有邀请码？点击填写（可选）'**
  String get inviteOptional;

  /// No description provided for @inviteHint.
  ///
  /// In zh, this message translates to:
  /// **'请输入 8 位邀请码'**
  String get inviteHint;

  /// No description provided for @inviteBonus.
  ///
  /// In zh, this message translates to:
  /// **'使用邀请码：你与邀请人本月各 +1 次分析'**
  String get inviteBonus;

  /// No description provided for @featureSwing.
  ///
  /// In zh, this message translates to:
  /// **'AI 挥杆分析，30 秒出报告'**
  String get featureSwing;

  /// No description provided for @featureCoach.
  ///
  /// In zh, this message translates to:
  /// **'24 小时 AI 教练在线问答'**
  String get featureCoach;

  /// No description provided for @featurePlan.
  ///
  /// In zh, this message translates to:
  /// **'个性化训练方案'**
  String get featurePlan;

  /// No description provided for @welcomeUse.
  ///
  /// In zh, this message translates to:
  /// **'欢迎使用'**
  String get welcomeUse;

  /// No description provided for @guestSubtitle1.
  ///
  /// In zh, this message translates to:
  /// **'可先了解产品与功能'**
  String get guestSubtitle1;

  /// No description provided for @guestSubtitle2.
  ///
  /// In zh, this message translates to:
  /// **'再选择是否登录'**
  String get guestSubtitle2;

  /// No description provided for @guestLegalHint.
  ///
  /// In zh, this message translates to:
  /// **'挥杆分析与 AI 对话需登录后使用。下方可查看示例报告与协议。'**
  String get guestLegalHint;

  /// No description provided for @loginToAnalyze.
  ///
  /// In zh, this message translates to:
  /// **'登录后开始分析'**
  String get loginToAnalyze;

  /// No description provided for @productOffers.
  ///
  /// In zh, this message translates to:
  /// **'本产品提供'**
  String get productOffers;

  /// No description provided for @guestFeatSwing.
  ///
  /// In zh, this message translates to:
  /// **'AI 挥杆分析，短视频出报告'**
  String get guestFeatSwing;

  /// No description provided for @guestFeatCoach.
  ///
  /// In zh, this message translates to:
  /// **'AI 教练在线答疑（生成式内容，仅供参考）'**
  String get guestFeatCoach;

  /// No description provided for @guestFeatPlan.
  ///
  /// In zh, this message translates to:
  /// **'基于分析的训练计划与打卡'**
  String get guestFeatPlan;

  /// No description provided for @sampleReportTitle.
  ///
  /// In zh, this message translates to:
  /// **'先看一份示例报告'**
  String get sampleReportTitle;

  /// No description provided for @sampleReportSubGuest.
  ///
  /// In zh, this message translates to:
  /// **'无需登录 · 不消耗次数'**
  String get sampleReportSubGuest;

  /// No description provided for @sampleReportSubUser.
  ///
  /// In zh, this message translates to:
  /// **'了解 AI 能给你什么 · 不消耗次数'**
  String get sampleReportSubUser;

  /// No description provided for @coachIntroTitle.
  ///
  /// In zh, this message translates to:
  /// **'AI 教练 · 了解能力'**
  String get coachIntroTitle;

  /// No description provided for @coachIntroSub.
  ///
  /// In zh, this message translates to:
  /// **'进入页内说明，对话前需登录'**
  String get coachIntroSub;

  /// No description provided for @helloGolfer.
  ///
  /// In zh, this message translates to:
  /// **'你好，{name} 👋'**
  String helloGolfer(String name);

  /// No description provided for @golferFallback.
  ///
  /// In zh, this message translates to:
  /// **'球友'**
  String get golferFallback;

  /// No description provided for @heroCta.
  ///
  /// In zh, this message translates to:
  /// **'拍一段挥杆，30 秒拿到 AI 专属报告'**
  String get heroCta;

  /// No description provided for @uploadNewSwing.
  ///
  /// In zh, this message translates to:
  /// **'+ 上传新挥杆'**
  String get uploadNewSwing;

  /// No description provided for @startFirstAnalysis.
  ///
  /// In zh, this message translates to:
  /// **'🎬 开始第一次分析'**
  String get startFirstAnalysis;

  /// No description provided for @quotaMemberUnlimited.
  ///
  /// In zh, this message translates to:
  /// **'会员 · 挥杆分析无限次'**
  String get quotaMemberUnlimited;

  /// No description provided for @quotaMonthRemaining.
  ///
  /// In zh, this message translates to:
  /// **'本月剩余分析 {remaining}/{total} 次'**
  String quotaMonthRemaining(int remaining, int total);

  /// No description provided for @statTotalAnalyses.
  ///
  /// In zh, this message translates to:
  /// **'累计分析'**
  String get statTotalAnalyses;

  /// No description provided for @statBestScore.
  ///
  /// In zh, this message translates to:
  /// **'最佳得分'**
  String get statBestScore;

  /// No description provided for @statStreak.
  ///
  /// In zh, this message translates to:
  /// **'连续天数'**
  String get statStreak;

  /// No description provided for @askCoach.
  ///
  /// In zh, this message translates to:
  /// **'问 AI 教练'**
  String get askCoach;

  /// No description provided for @memberUnlimited.
  ///
  /// In zh, this message translates to:
  /// **'会员无限次'**
  String get memberUnlimited;

  /// No description provided for @chatRemainingToday.
  ///
  /// In zh, this message translates to:
  /// **'今日剩余 {n} 次'**
  String chatRemainingToday(int n);

  /// No description provided for @recentAnalyses.
  ///
  /// In zh, this message translates to:
  /// **'最近分析'**
  String get recentAnalyses;

  /// No description provided for @viewAll.
  ///
  /// In zh, this message translates to:
  /// **'查看全部 ›'**
  String get viewAll;

  /// No description provided for @noAnalysesYet.
  ///
  /// In zh, this message translates to:
  /// **'还没有分析记录，上传第一段挥杆吧'**
  String get noAnalysesYet;

  /// No description provided for @statusFailed.
  ///
  /// In zh, this message translates to:
  /// **'失败'**
  String get statusFailed;

  /// No description provided for @statusAnalyzing.
  ///
  /// In zh, this message translates to:
  /// **'分析中'**
  String get statusAnalyzing;

  /// No description provided for @quotaExhaustedTitle.
  ///
  /// In zh, this message translates to:
  /// **'本月分析次数已用完'**
  String get quotaExhaustedTitle;

  /// No description provided for @quotaExhaustedBody.
  ///
  /// In zh, this message translates to:
  /// **'本月免费分析次数已用完。请下月额度刷新后再试，或等待后续 App 内购买会员上线。'**
  String get quotaExhaustedBody;

  /// No description provided for @gotIt.
  ///
  /// In zh, this message translates to:
  /// **'我知道了'**
  String get gotIt;

  /// No description provided for @viewBenefits.
  ///
  /// In zh, this message translates to:
  /// **'查看权益说明'**
  String get viewBenefits;

  /// No description provided for @todayAt.
  ///
  /// In zh, this message translates to:
  /// **'今天 {time}'**
  String todayAt(String time);

  /// No description provided for @scoreUnit.
  ///
  /// In zh, this message translates to:
  /// **' 分'**
  String get scoreUnit;

  /// No description provided for @latestShot.
  ///
  /// In zh, this message translates to:
  /// **'最近一杆'**
  String get latestShot;

  /// No description provided for @analysisDone.
  ///
  /// In zh, this message translates to:
  /// **'已完成分析'**
  String get analysisDone;

  /// No description provided for @settings.
  ///
  /// In zh, this message translates to:
  /// **'设置'**
  String get settings;

  /// No description provided for @sectionExperience.
  ///
  /// In zh, this message translates to:
  /// **'体验'**
  String get sectionExperience;

  /// No description provided for @replayCaptureGuide.
  ///
  /// In zh, this message translates to:
  /// **'重新查看拍摄指南'**
  String get replayCaptureGuide;

  /// No description provided for @guideResetToast.
  ///
  /// In zh, this message translates to:
  /// **'已重置，下次分析会再次显示拍摄指南'**
  String get guideResetToast;

  /// No description provided for @clearCache.
  ///
  /// In zh, this message translates to:
  /// **'清除本地缓存'**
  String get clearCache;

  /// No description provided for @clearCacheBody.
  ///
  /// In zh, this message translates to:
  /// **'将清除本地登录态与设置缓存，需要重新登录。确认继续？'**
  String get clearCacheBody;

  /// No description provided for @cancel.
  ///
  /// In zh, this message translates to:
  /// **'取消'**
  String get cancel;

  /// No description provided for @confirmClear.
  ///
  /// In zh, this message translates to:
  /// **'清除'**
  String get confirmClear;

  /// No description provided for @sectionLegal.
  ///
  /// In zh, this message translates to:
  /// **'法律与协议'**
  String get sectionLegal;

  /// No description provided for @aboutApp.
  ///
  /// In zh, this message translates to:
  /// **'关于领翼golf'**
  String get aboutApp;

  /// No description provided for @deleteAccount.
  ///
  /// In zh, this message translates to:
  /// **'注销账号'**
  String get deleteAccount;

  /// No description provided for @logout.
  ///
  /// In zh, this message translates to:
  /// **'退出登录'**
  String get logout;

  /// No description provided for @logoutConfirm.
  ///
  /// In zh, this message translates to:
  /// **'确认退出登录？'**
  String get logoutConfirm;

  /// No description provided for @prompt.
  ///
  /// In zh, this message translates to:
  /// **'提示'**
  String get prompt;

  /// No description provided for @membershipCenter.
  ///
  /// In zh, this message translates to:
  /// **'会员中心'**
  String get membershipCenter;

  /// No description provided for @freeUser.
  ///
  /// In zh, this message translates to:
  /// **'免费用户'**
  String get freeUser;

  /// No description provided for @memberThanks.
  ///
  /// In zh, this message translates to:
  /// **'感谢支持，尽情享受全部会员权益'**
  String get memberThanks;

  /// No description provided for @membershipFreeHint.
  ///
  /// In zh, this message translates to:
  /// **'本版本 App 提供免费额度；会员购买能力将通过苹果 App 内购买提供'**
  String get membershipFreeHint;

  /// No description provided for @membershipNoIap.
  ///
  /// In zh, this message translates to:
  /// **'当前版本暂不在 App 内开通付费会员。请继续使用免费分析与对话额度；后续若提供会员订阅，将仅通过苹果 App 内购买完成。'**
  String get membershipNoIap;

  /// No description provided for @memberYearly.
  ///
  /// In zh, this message translates to:
  /// **'年度会员'**
  String get memberYearly;

  /// No description provided for @memberMonthly.
  ///
  /// In zh, this message translates to:
  /// **'月度会员'**
  String get memberMonthly;

  /// No description provided for @memberGeneric.
  ///
  /// In zh, this message translates to:
  /// **'会员'**
  String get memberGeneric;

  /// No description provided for @memberRemainingDays.
  ///
  /// In zh, this message translates to:
  /// **'{label} · 还剩 {days} 天'**
  String memberRemainingDays(String label, int days);

  /// No description provided for @benefitSwing.
  ///
  /// In zh, this message translates to:
  /// **'挥杆视频分析'**
  String get benefitSwing;

  /// No description provided for @benefitCoach.
  ///
  /// In zh, this message translates to:
  /// **'AI 教练对话'**
  String get benefitCoach;

  /// No description provided for @benefitPlan.
  ///
  /// In zh, this message translates to:
  /// **'本周训练计划'**
  String get benefitPlan;

  /// No description provided for @benefitCurve.
  ///
  /// In zh, this message translates to:
  /// **'进步曲线'**
  String get benefitCurve;

  /// No description provided for @benefitCompare.
  ///
  /// In zh, this message translates to:
  /// **'历史报告对比'**
  String get benefitCompare;

  /// No description provided for @tierLimitedMonth.
  ///
  /// In zh, this message translates to:
  /// **'每月有限次数'**
  String get tierLimitedMonth;

  /// No description provided for @tierLimitedDay.
  ///
  /// In zh, this message translates to:
  /// **'每日有限次数'**
  String get tierLimitedDay;

  /// No description provided for @tierViewOnly.
  ///
  /// In zh, this message translates to:
  /// **'仅查看'**
  String get tierViewOnly;

  /// No description provided for @tierBasic.
  ///
  /// In zh, this message translates to:
  /// **'基础'**
  String get tierBasic;

  /// No description provided for @tierUnlimited.
  ///
  /// In zh, this message translates to:
  /// **'无限次'**
  String get tierUnlimited;

  /// No description provided for @tierFullPlan.
  ///
  /// In zh, this message translates to:
  /// **'完整个性化'**
  String get tierFullPlan;

  /// No description provided for @tierFullHistory.
  ///
  /// In zh, this message translates to:
  /// **'完整历史与折线'**
  String get tierFullHistory;

  /// No description provided for @tierSideBySide.
  ///
  /// In zh, this message translates to:
  /// **'并排对比'**
  String get tierSideBySide;

  /// No description provided for @helpCenter.
  ///
  /// In zh, this message translates to:
  /// **'帮助中心'**
  String get helpCenter;

  /// No description provided for @faqShootQ.
  ///
  /// In zh, this message translates to:
  /// **'如何拍摄一段合格的挥杆视频？'**
  String get faqShootQ;

  /// No description provided for @faqShootA.
  ///
  /// In zh, this message translates to:
  /// **'建议在光线充足的场地，手机横屏或竖屏固定，完整拍下从预备到收杆的动作；正面（Face-On）或侧面（Down-the-Line）机位皆可，时长 2-30 秒。'**
  String get faqShootA;

  /// No description provided for @faqHowLongQ.
  ///
  /// In zh, this message translates to:
  /// **'分析需要多久？'**
  String get faqHowLongQ;

  /// No description provided for @faqHowLongA.
  ///
  /// In zh, this message translates to:
  /// **'视频上传后，AI 通常在 30 秒内完成分析并生成报告，弱网时可能稍长。'**
  String get faqHowLongA;

  /// No description provided for @faqQuotaQ.
  ///
  /// In zh, this message translates to:
  /// **'分析次数用完了怎么办？'**
  String get faqQuotaQ;

  /// No description provided for @faqQuotaA.
  ///
  /// In zh, this message translates to:
  /// **'免费额度每月刷新。本版本 App 内暂不提供付费会员购买；后续若开通将通过苹果 App 内购买。'**
  String get faqQuotaA;

  /// No description provided for @faqCoachQ.
  ///
  /// In zh, this message translates to:
  /// **'AI 教练能回答哪些问题？'**
  String get faqCoachQ;

  /// No description provided for @faqCoachA.
  ///
  /// In zh, this message translates to:
  /// **'挥杆技术、训练计划、规则疑问、装备选择等高尔夫相关问题都可以问。'**
  String get faqCoachA;

  /// No description provided for @faqDataQ.
  ///
  /// In zh, this message translates to:
  /// **'我的数据安全吗？'**
  String get faqDataQ;

  /// No description provided for @faqDataA.
  ///
  /// In zh, this message translates to:
  /// **'挥杆视频与账号数据由本公司云端处理；对话类生成可能经国内大模型（如 DeepSeek）。你可随时在「我的」删除或注销账号。'**
  String get faqDataA;

  /// No description provided for @aiConsentTitle.
  ///
  /// In zh, this message translates to:
  /// **'AI 数据处理说明'**
  String get aiConsentTitle;

  /// No description provided for @aiConsentSwing.
  ///
  /// In zh, this message translates to:
  /// **'将上传你选择的挥杆视频及相关参数（球杆、机位等），用于生成分析报告。'**
  String get aiConsentSwing;

  /// No description provided for @aiConsentChat.
  ///
  /// In zh, this message translates to:
  /// **'将发送你输入的对话文本及必要上下文，用于生成 AI 教练回复。'**
  String get aiConsentChat;

  /// No description provided for @aiConsentReceivers.
  ///
  /// In zh, this message translates to:
  /// **'接收方：'**
  String get aiConsentReceivers;

  /// No description provided for @aiConsentOurCloud.
  ///
  /// In zh, this message translates to:
  /// **'领翼golf 云端服务（北京思无界控股有限公司）'**
  String get aiConsentOurCloud;

  /// No description provided for @aiConsentProvider.
  ///
  /// In zh, this message translates to:
  /// **'DeepSeek（深度求索）等大模型服务商（处理对话/文案类生成时）'**
  String get aiConsentProvider;

  /// No description provided for @aiConsentPurpose.
  ///
  /// In zh, this message translates to:
  /// **'用途：仅为你提供本产品的挥杆分析或 AI 答疑，不会出售你的个人信息。在你未另行单独同意前，不会将可识别你身份的内容用于无关模型训练。\n\n详情见《隐私政策》。是否同意继续？'**
  String get aiConsentPurpose;

  /// No description provided for @disagree.
  ///
  /// In zh, this message translates to:
  /// **'不同意'**
  String get disagree;

  /// No description provided for @agreeContinue.
  ///
  /// In zh, this message translates to:
  /// **'同意并继续'**
  String get agreeContinue;

  /// No description provided for @coachWelcome.
  ///
  /// In zh, this message translates to:
  /// **'你好！我是领翼golf 的 AI 高尔夫教练。随时问我挥杆技术、练习方法或高尔夫知识方面的问题。'**
  String get coachWelcome;

  /// No description provided for @chatQuotaExhausted.
  ///
  /// In zh, this message translates to:
  /// **'今日对话次数已用完'**
  String get chatQuotaExhausted;

  /// No description provided for @rateLimited.
  ///
  /// In zh, this message translates to:
  /// **'操作太快了，稍等片刻再试'**
  String get rateLimited;

  /// No description provided for @clearChatTitle.
  ///
  /// In zh, this message translates to:
  /// **'清空对话？'**
  String get clearChatTitle;

  /// No description provided for @clearChatStreaming.
  ///
  /// In zh, this message translates to:
  /// **'当前 AI 正在回复，点击清空会立即中断。'**
  String get clearChatStreaming;

  /// No description provided for @clearChatBody.
  ///
  /// In zh, this message translates to:
  /// **'会删除本次会话的全部历史，AI 将以新会话身份开始。'**
  String get clearChatBody;

  /// No description provided for @clearAction.
  ///
  /// In zh, this message translates to:
  /// **'清空'**
  String get clearAction;

  /// No description provided for @loginToChat.
  ///
  /// In zh, this message translates to:
  /// **'登录后与 AI 教练对话'**
  String get loginToChat;

  /// No description provided for @connectingCoach.
  ///
  /// In zh, this message translates to:
  /// **'正在接入 AI 教练...'**
  String get connectingCoach;

  /// No description provided for @loadFailed.
  ///
  /// In zh, this message translates to:
  /// **'加载失败'**
  String get loadFailed;

  /// No description provided for @reload.
  ///
  /// In zh, this message translates to:
  /// **'重新加载'**
  String get reload;

  /// No description provided for @reportBasedChat.
  ///
  /// In zh, this message translates to:
  /// **'基于报告的对话'**
  String get reportBasedChat;

  /// No description provided for @viewOriginalReport.
  ///
  /// In zh, this message translates to:
  /// **'查看原报告 ›'**
  String get viewOriginalReport;

  /// No description provided for @tryThese.
  ///
  /// In zh, this message translates to:
  /// **'试试这些问题：'**
  String get tryThese;

  /// No description provided for @needsAnalysis.
  ///
  /// In zh, this message translates to:
  /// **'需分析'**
  String get needsAnalysis;

  /// No description provided for @needUploadFirstTitle.
  ///
  /// In zh, this message translates to:
  /// **'需要先上传一次挥杆'**
  String get needUploadFirstTitle;

  /// No description provided for @needUploadFirstBody.
  ///
  /// In zh, this message translates to:
  /// **'这个问题需要结合你的挥杆分析，先去「首页 → 开始分析」拍一次吧。'**
  String get needUploadFirstBody;

  /// No description provided for @copied.
  ///
  /// In zh, this message translates to:
  /// **'已复制'**
  String get copied;

  /// No description provided for @chatUsedUp.
  ///
  /// In zh, this message translates to:
  /// **'今日已用完'**
  String get chatUsedUp;

  /// No description provided for @chatRemainFrac.
  ///
  /// In zh, this message translates to:
  /// **'今日剩余 {remaining}/{total} 次'**
  String chatRemainFrac(int remaining, int total);

  /// No description provided for @chatUsedUpHint.
  ///
  /// In zh, this message translates to:
  /// **'今日对话已用完'**
  String get chatUsedUpHint;

  /// No description provided for @aiReplying.
  ///
  /// In zh, this message translates to:
  /// **'AI 正在回复，稍等片刻...'**
  String get aiReplying;

  /// No description provided for @askCoachHint.
  ///
  /// In zh, this message translates to:
  /// **'问问 AI 教练...'**
  String get askCoachHint;

  /// No description provided for @me.
  ///
  /// In zh, this message translates to:
  /// **'我'**
  String get me;

  /// No description provided for @tapRetry.
  ///
  /// In zh, this message translates to:
  /// **'↻ 点击重试'**
  String get tapRetry;

  /// No description provided for @training.
  ///
  /// In zh, this message translates to:
  /// **'训练'**
  String get training;

  /// No description provided for @loginToSeePlan.
  ///
  /// In zh, this message translates to:
  /// **'登录后查看训练计划'**
  String get loginToSeePlan;

  /// No description provided for @loginToSeeCalendar.
  ///
  /// In zh, this message translates to:
  /// **'打卡日历与进步曲线也会在登录后展示'**
  String get loginToSeeCalendar;

  /// No description provided for @checkinFailed.
  ///
  /// In zh, this message translates to:
  /// **'打卡失败，请稍后重试'**
  String get checkinFailed;

  /// No description provided for @checkinOk.
  ///
  /// In zh, this message translates to:
  /// **'打卡成功！'**
  String get checkinOk;

  /// No description provided for @checkinStreak.
  ///
  /// In zh, this message translates to:
  /// **'打卡成功！连续 {n} 天'**
  String checkinStreak(int n);

  /// No description provided for @checkinSuggestReshoot.
  ///
  /// In zh, this message translates to:
  /// **'建议用相同机位再拍一次挥杆，对比是否改善。'**
  String get checkinSuggestReshoot;

  /// No description provided for @later.
  ///
  /// In zh, this message translates to:
  /// **'稍后再说'**
  String get later;

  /// No description provided for @goCapture.
  ///
  /// In zh, this message translates to:
  /// **'去拍摄'**
  String get goCapture;

  /// No description provided for @practiceCalendar.
  ///
  /// In zh, this message translates to:
  /// **'练习日历'**
  String get practiceCalendar;

  /// No description provided for @progressCurve.
  ///
  /// In zh, this message translates to:
  /// **'进步曲线'**
  String get progressCurve;

  /// No description provided for @last90.
  ///
  /// In zh, this message translates to:
  /// **'近 90 天'**
  String get last90;

  /// No description provided for @allTime.
  ///
  /// In zh, this message translates to:
  /// **'全部'**
  String get allTime;

  /// No description provided for @progressHint.
  ///
  /// In zh, this message translates to:
  /// **'完成分析后可查看得分趋势；会员可见更完整曲线。'**
  String get progressHint;

  /// No description provided for @noPlanTitle.
  ///
  /// In zh, this message translates to:
  /// **'还没有训练计划'**
  String get noPlanTitle;

  /// No description provided for @noPlanBody.
  ///
  /// In zh, this message translates to:
  /// **'先上传一次挥杆视频，AI 会根据分析结果为你生成本周专属训练'**
  String get noPlanBody;

  /// No description provided for @goUpload.
  ///
  /// In zh, this message translates to:
  /// **'去上传视频'**
  String get goUpload;

  /// No description provided for @taskCount.
  ///
  /// In zh, this message translates to:
  /// **'{n} 个任务'**
  String taskCount(int n);

  /// No description provided for @loadFailedRetry.
  ///
  /// In zh, this message translates to:
  /// **'加载失败，请稍后再试'**
  String get loadFailedRetry;

  /// No description provided for @weekPlan.
  ///
  /// In zh, this message translates to:
  /// **'本周训练'**
  String get weekPlan;

  /// No description provided for @completed.
  ///
  /// In zh, this message translates to:
  /// **'已完成'**
  String get completed;

  /// No description provided for @pending.
  ///
  /// In zh, this message translates to:
  /// **'待完成'**
  String get pending;

  /// No description provided for @streakDays.
  ///
  /// In zh, this message translates to:
  /// **'连续打卡 {n} 天'**
  String streakDays(int n);

  /// No description provided for @submitting.
  ///
  /// In zh, this message translates to:
  /// **'提交中…'**
  String get submitting;

  /// No description provided for @completeCheckin.
  ///
  /// In zh, this message translates to:
  /// **'完成打卡'**
  String get completeCheckin;

  /// No description provided for @profileSyncHint.
  ///
  /// In zh, this message translates to:
  /// **'登录后同步个人资料与分析记录'**
  String get profileSyncHint;

  /// No description provided for @myReports.
  ///
  /// In zh, this message translates to:
  /// **'我的分析报告'**
  String get myReports;

  /// No description provided for @coachChat.
  ///
  /// In zh, this message translates to:
  /// **'AI 教练对话'**
  String get coachChat;

  /// No description provided for @myClubs.
  ///
  /// In zh, this message translates to:
  /// **'我的装备'**
  String get myClubs;

  /// No description provided for @lessons.
  ///
  /// In zh, this message translates to:
  /// **'课程学习'**
  String get lessons;

  /// No description provided for @proLibrary.
  ///
  /// In zh, this message translates to:
  /// **'球手对比库'**
  String get proLibrary;

  /// No description provided for @meetup.
  ///
  /// In zh, this message translates to:
  /// **'约球邀请'**
  String get meetup;

  /// No description provided for @deletionPending.
  ///
  /// In zh, this message translates to:
  /// **'账号已排期注销，点此查看或撤销'**
  String get deletionPending;

  /// No description provided for @edit.
  ///
  /// In zh, this message translates to:
  /// **'编辑'**
  String get edit;

  /// No description provided for @golfProfile.
  ///
  /// In zh, this message translates to:
  /// **'高尔夫档案'**
  String get golfProfile;

  /// No description provided for @modify.
  ///
  /// In zh, this message translates to:
  /// **'修改'**
  String get modify;

  /// No description provided for @level.
  ///
  /// In zh, this message translates to:
  /// **'水平'**
  String get level;

  /// No description provided for @goals.
  ///
  /// In zh, this message translates to:
  /// **'目标'**
  String get goals;

  /// No description provided for @practiceFreq.
  ///
  /// In zh, this message translates to:
  /// **'练习频率'**
  String get practiceFreq;

  /// No description provided for @notSet.
  ///
  /// In zh, this message translates to:
  /// **'未设置'**
  String get notSet;

  /// No description provided for @statAnalyses.
  ///
  /// In zh, this message translates to:
  /// **'分析次数'**
  String get statAnalyses;

  /// No description provided for @statCheckin.
  ///
  /// In zh, this message translates to:
  /// **'连续打卡'**
  String get statCheckin;

  /// No description provided for @statHighScore.
  ///
  /// In zh, this message translates to:
  /// **'最高分'**
  String get statHighScore;

  /// No description provided for @consentWelcome.
  ///
  /// In zh, this message translates to:
  /// **'欢迎使用领翼golf'**
  String get consentWelcome;

  /// No description provided for @consentBefore.
  ///
  /// In zh, this message translates to:
  /// **'在开始之前'**
  String get consentBefore;

  /// No description provided for @consentIntro.
  ///
  /// In zh, this message translates to:
  /// **'我们非常重视你的个人信息保护。使用本产品，我们需要收集：'**
  String get consentIntro;

  /// No description provided for @consentBulletApple.
  ///
  /// In zh, this message translates to:
  /// **'Apple 账号标识：用于 Sign in with Apple 登录与账号识别。'**
  String get consentBulletApple;

  /// No description provided for @consentBulletVideo.
  ///
  /// In zh, this message translates to:
  /// **'挥杆视频：仅在你主动拍摄/选择并同意后上传，用于 AI 分析并生成报告（本公司云端）。'**
  String get consentBulletVideo;

  /// No description provided for @consentBulletChat.
  ///
  /// In zh, this message translates to:
  /// **'对话内容：用于 AI 教练问答；经你同意后通过大模型（如 DeepSeek）生成回复。'**
  String get consentBulletChat;

  /// No description provided for @consentStorage.
  ///
  /// In zh, this message translates to:
  /// **'数据由本公司云端处理；对话类可能经国内大模型。你可在「我的」随时查看、删除或注销账号。'**
  String get consentStorage;

  /// No description provided for @consentDisagreeExit.
  ///
  /// In zh, this message translates to:
  /// **'若暂不同意，请退出。你可以随时重新进入并选择同意。'**
  String get consentDisagreeExit;

  /// No description provided for @notNow.
  ///
  /// In zh, this message translates to:
  /// **'暂不同意'**
  String get notNow;

  /// No description provided for @disagreeCannotUse.
  ///
  /// In zh, this message translates to:
  /// **'不同意将无法使用本产品'**
  String get disagreeCannotUse;

  /// No description provided for @withWord.
  ///
  /// In zh, this message translates to:
  /// **'与'**
  String get withWord;

  /// No description provided for @colBenefit.
  ///
  /// In zh, this message translates to:
  /// **'权益'**
  String get colBenefit;

  /// No description provided for @colFree.
  ///
  /// In zh, this message translates to:
  /// **'免费'**
  String get colFree;

  /// No description provided for @listSep.
  ///
  /// In zh, this message translates to:
  /// **'、'**
  String get listSep;

  /// No description provided for @weekdayMon.
  ///
  /// In zh, this message translates to:
  /// **'一'**
  String get weekdayMon;

  /// No description provided for @weekdayTue.
  ///
  /// In zh, this message translates to:
  /// **'二'**
  String get weekdayTue;

  /// No description provided for @weekdayWed.
  ///
  /// In zh, this message translates to:
  /// **'三'**
  String get weekdayWed;

  /// No description provided for @weekdayThu.
  ///
  /// In zh, this message translates to:
  /// **'四'**
  String get weekdayThu;

  /// No description provided for @weekdayFri.
  ///
  /// In zh, this message translates to:
  /// **'五'**
  String get weekdayFri;

  /// No description provided for @weekdaySat.
  ///
  /// In zh, this message translates to:
  /// **'六'**
  String get weekdaySat;

  /// No description provided for @weekdaySun.
  ///
  /// In zh, this message translates to:
  /// **'日'**
  String get weekdaySun;

  /// No description provided for @dateWeekday.
  ///
  /// In zh, this message translates to:
  /// **'{md} 周{wd}'**
  String dateWeekday(String md, String wd);

  /// No description provided for @levelBeginner.
  ///
  /// In zh, this message translates to:
  /// **'初学者'**
  String get levelBeginner;

  /// No description provided for @levelElementary.
  ///
  /// In zh, this message translates to:
  /// **'初级'**
  String get levelElementary;

  /// No description provided for @levelIntermediate.
  ///
  /// In zh, this message translates to:
  /// **'中级'**
  String get levelIntermediate;

  /// No description provided for @levelAdvanced.
  ///
  /// In zh, this message translates to:
  /// **'高级'**
  String get levelAdvanced;

  /// No description provided for @goalDistance.
  ///
  /// In zh, this message translates to:
  /// **'提升距离'**
  String get goalDistance;

  /// No description provided for @goalAccuracy.
  ///
  /// In zh, this message translates to:
  /// **'提升准度'**
  String get goalAccuracy;

  /// No description provided for @goalShortGame.
  ///
  /// In zh, this message translates to:
  /// **'短杆球技'**
  String get goalShortGame;

  /// No description provided for @goalPutting.
  ///
  /// In zh, this message translates to:
  /// **'推杆技术'**
  String get goalPutting;

  /// No description provided for @goalConsistency.
  ///
  /// In zh, this message translates to:
  /// **'一致性'**
  String get goalConsistency;

  /// No description provided for @freqOccasional.
  ///
  /// In zh, this message translates to:
  /// **'偶尔'**
  String get freqOccasional;

  /// No description provided for @freqOnce.
  ///
  /// In zh, this message translates to:
  /// **'每周 1 次'**
  String get freqOnce;

  /// No description provided for @freqFrequent.
  ///
  /// In zh, this message translates to:
  /// **'每周 2-3 次'**
  String get freqFrequent;

  /// No description provided for @freqDaily.
  ///
  /// In zh, this message translates to:
  /// **'几乎每天'**
  String get freqDaily;

  /// No description provided for @captureTitle.
  ///
  /// In zh, this message translates to:
  /// **'挥杆分析'**
  String get captureTitle;

  /// No description provided for @captureOnlyMp4Mov.
  ///
  /// In zh, this message translates to:
  /// **'仅支持 mp4 / mov 视频'**
  String get captureOnlyMp4Mov;

  /// No description provided for @captureTooLarge.
  ///
  /// In zh, this message translates to:
  /// **'视频不能超过 100MB'**
  String get captureTooLarge;

  /// No description provided for @captureTooShort.
  ///
  /// In zh, this message translates to:
  /// **'视频太短（需 ≥ {n}s）'**
  String captureTooShort(int n);

  /// No description provided for @captureTooLong.
  ///
  /// In zh, this message translates to:
  /// **'视频太长（需 ≤ {n}s）'**
  String captureTooLong(int n);

  /// No description provided for @capturePickFailed.
  ///
  /// In zh, this message translates to:
  /// **'选取视频失败：{error}'**
  String capturePickFailed(String error);

  /// No description provided for @captureNeedVideo.
  ///
  /// In zh, this message translates to:
  /// **'请先拍摄或选择挥杆视频'**
  String get captureNeedVideo;

  /// No description provided for @captureLimits.
  ///
  /// In zh, this message translates to:
  /// **'时长 {min}-{max} s · 大小 ≤ {mb}MB · 支持 {ext}'**
  String captureLimits(int min, int max, int mb, String ext);

  /// No description provided for @captureNextParams.
  ///
  /// In zh, this message translates to:
  /// **'下一步：选择参数'**
  String get captureNextParams;

  /// No description provided for @captureTrySample.
  ///
  /// In zh, this message translates to:
  /// **'先用示例视频体验一下'**
  String get captureTrySample;

  /// No description provided for @captureCenterSubject.
  ///
  /// In zh, this message translates to:
  /// **'对准人物 · 居中入画'**
  String get captureCenterSubject;

  /// No description provided for @captureTipFraming.
  ///
  /// In zh, this message translates to:
  /// **'将球员放在画面中央，脚到头部全部露出'**
  String get captureTipFraming;

  /// No description provided for @captureTipLength.
  ///
  /// In zh, this message translates to:
  /// **'拍满至少 2 秒（建议 3–5 秒），只录 1 次完整挥杆'**
  String get captureTipLength;

  /// No description provided for @captureTipLight.
  ///
  /// In zh, this message translates to:
  /// **'优选自然光，避免强背光和严重抖动'**
  String get captureTipLight;

  /// No description provided for @capturePrompt.
  ///
  /// In zh, this message translates to:
  /// **'拍摄或选择一段挥杆视频（2-30 秒）'**
  String get capturePrompt;

  /// No description provided for @captureSelected.
  ///
  /// In zh, this message translates to:
  /// **'已选择 · {duration}s · {size}MB'**
  String captureSelected(String duration, String size);

  /// No description provided for @record.
  ///
  /// In zh, this message translates to:
  /// **'录制'**
  String get record;

  /// No description provided for @album.
  ///
  /// In zh, this message translates to:
  /// **'相册'**
  String get album;

  /// No description provided for @paramsTitle.
  ///
  /// In zh, this message translates to:
  /// **'分析参数'**
  String get paramsTitle;

  /// No description provided for @paramsMode.
  ///
  /// In zh, this message translates to:
  /// **'分析模式'**
  String get paramsMode;

  /// No description provided for @paramsModeHint.
  ///
  /// In zh, this message translates to:
  /// **'推杆/切杆需服务端灰度开启；若创建失败请改回全挥杆。'**
  String get paramsModeHint;

  /// No description provided for @paramsClub.
  ///
  /// In zh, this message translates to:
  /// **'球杆'**
  String get paramsClub;

  /// No description provided for @paramsCamera.
  ///
  /// In zh, this message translates to:
  /// **'拍摄机位'**
  String get paramsCamera;

  /// No description provided for @paramsUploading.
  ///
  /// In zh, this message translates to:
  /// **'上传中…'**
  String get paramsUploading;

  /// No description provided for @paramsDetecting.
  ///
  /// In zh, this message translates to:
  /// **'识别挥杆段…'**
  String get paramsDetecting;

  /// No description provided for @paramsCreating.
  ///
  /// In zh, this message translates to:
  /// **'创建分析任务…'**
  String get paramsCreating;

  /// No description provided for @paramsStartFailed.
  ///
  /// In zh, this message translates to:
  /// **'发起分析失败'**
  String get paramsStartFailed;

  /// No description provided for @paramsProcessing.
  ///
  /// In zh, this message translates to:
  /// **'处理中…'**
  String get paramsProcessing;

  /// No description provided for @paramsStart.
  ///
  /// In zh, this message translates to:
  /// **'开始分析'**
  String get paramsStart;

  /// No description provided for @modeFullSwing.
  ///
  /// In zh, this message translates to:
  /// **'全挥杆'**
  String get modeFullSwing;

  /// No description provided for @modeFullSwingSub.
  ///
  /// In zh, this message translates to:
  /// **'铁木杆 / 一号木'**
  String get modeFullSwingSub;

  /// No description provided for @modePutting.
  ///
  /// In zh, this message translates to:
  /// **'推杆'**
  String get modePutting;

  /// No description provided for @modePuttingSub.
  ///
  /// In zh, this message translates to:
  /// **'果岭推杆'**
  String get modePuttingSub;

  /// No description provided for @modeChipping.
  ///
  /// In zh, this message translates to:
  /// **'切杆'**
  String get modeChipping;

  /// No description provided for @modeChippingSub.
  ///
  /// In zh, this message translates to:
  /// **'短切 / 劈起'**
  String get modeChippingSub;

  /// No description provided for @waitingReceived.
  ///
  /// In zh, this message translates to:
  /// **'视频已接收'**
  String get waitingReceived;

  /// No description provided for @waitingPose.
  ///
  /// In zh, this message translates to:
  /// **'识别人体姿态'**
  String get waitingPose;

  /// No description provided for @waitingSwing.
  ///
  /// In zh, this message translates to:
  /// **'分析挥杆动作'**
  String get waitingSwing;

  /// No description provided for @waitingDiagnose.
  ///
  /// In zh, this message translates to:
  /// **'生成诊断建议'**
  String get waitingDiagnose;

  /// No description provided for @waitingRender.
  ///
  /// In zh, this message translates to:
  /// **'渲染分析报告'**
  String get waitingRender;

  /// No description provided for @waitingDone.
  ///
  /// In zh, this message translates to:
  /// **'分析完成'**
  String get waitingDone;

  /// No description provided for @waitingInProgress.
  ///
  /// In zh, this message translates to:
  /// **'AI 正在分析你的挥杆'**
  String get waitingInProgress;

  /// No description provided for @waitingOpening.
  ///
  /// In zh, this message translates to:
  /// **'即将为你打开报告…'**
  String get waitingOpening;

  /// No description provided for @waitingEtaSeconds.
  ///
  /// In zh, this message translates to:
  /// **'预计还需 {n} 秒'**
  String waitingEtaSeconds(int n);

  /// No description provided for @waitingEtaSoon.
  ///
  /// In zh, this message translates to:
  /// **'预计还需不到 30 秒'**
  String get waitingEtaSoon;

  /// No description provided for @waitingSlowHint.
  ///
  /// In zh, this message translates to:
  /// **'分析可能比预期稍久，请耐心等待；仍可留在本页或稍后在「我的分析报告」查看结果。'**
  String get waitingSlowHint;

  /// No description provided for @waitingSlowTitle.
  ///
  /// In zh, this message translates to:
  /// **'⏳ 分析时间比预期长'**
  String get waitingSlowTitle;

  /// No description provided for @waitingSlowBody.
  ///
  /// In zh, this message translates to:
  /// **'别担心，任务还在后台跑。完成后你可以在「我的分析报告」里查看结果。你也可以先去首页做点别的。'**
  String get waitingSlowBody;

  /// No description provided for @waitingBackHome.
  ///
  /// In zh, this message translates to:
  /// **'先回首页'**
  String get waitingBackHome;

  /// No description provided for @waitingDidYouKnow.
  ///
  /// In zh, this message translates to:
  /// **'{category}  ·  你知道吗？'**
  String waitingDidYouKnow(String category);

  /// No description provided for @waitingFailed.
  ///
  /// In zh, this message translates to:
  /// **'分析失败'**
  String get waitingFailed;

  /// No description provided for @waitingReshoot.
  ///
  /// In zh, this message translates to:
  /// **'重新拍摄'**
  String get waitingReshoot;

  /// No description provided for @waitingGoHome.
  ///
  /// In zh, this message translates to:
  /// **'去首页'**
  String get waitingGoHome;

  /// No description provided for @reportLoading.
  ///
  /// In zh, this message translates to:
  /// **'加载报告中…'**
  String get reportLoading;

  /// No description provided for @reportLoadFailed.
  ///
  /// In zh, this message translates to:
  /// **'报告加载失败'**
  String get reportLoadFailed;

  /// No description provided for @retry.
  ///
  /// In zh, this message translates to:
  /// **'重试'**
  String get retry;

  /// No description provided for @scoreGuideLink.
  ///
  /// In zh, this message translates to:
  /// **'分数说明 ›'**
  String get scoreGuideLink;

  /// No description provided for @sampleReportBanner.
  ///
  /// In zh, this message translates to:
  /// **'这是演示报告，用真实数据展示 AI 能发现的问题；不消耗你的分析次数。'**
  String get sampleReportBanner;

  /// No description provided for @clipOriginal.
  ///
  /// In zh, this message translates to:
  /// **'原片'**
  String get clipOriginal;

  /// No description provided for @clipSkeleton.
  ///
  /// In zh, this message translates to:
  /// **'骨骼'**
  String get clipSkeleton;

  /// No description provided for @playbackSpeed.
  ///
  /// In zh, this message translates to:
  /// **'倍速'**
  String get playbackSpeed;

  /// No description provided for @vsLastSameType.
  ///
  /// In zh, this message translates to:
  /// **'较最近一次同类型'**
  String get vsLastSameType;

  /// No description provided for @highlightsThisSwing.
  ///
  /// In zh, this message translates to:
  /// **'本次亮点'**
  String get highlightsThisSwing;

  /// No description provided for @filmingTips.
  ///
  /// In zh, this message translates to:
  /// **'拍摄提示'**
  String get filmingTips;

  /// No description provided for @sixDimScores.
  ///
  /// In zh, this message translates to:
  /// **'六维评分'**
  String get sixDimScores;

  /// No description provided for @tapPhaseToJump.
  ///
  /// In zh, this message translates to:
  /// **'点击阶段跳到对应画面'**
  String get tapPhaseToJump;

  /// No description provided for @mostNeedImprove.
  ///
  /// In zh, this message translates to:
  /// **'最需改进'**
  String get mostNeedImprove;

  /// No description provided for @otherIssues.
  ///
  /// In zh, this message translates to:
  /// **'其他问题'**
  String get otherIssues;

  /// No description provided for @issueDiagnosis.
  ///
  /// In zh, this message translates to:
  /// **'问题诊断'**
  String get issueDiagnosis;

  /// No description provided for @weeklyFocus.
  ///
  /// In zh, this message translates to:
  /// **'本周主攻'**
  String get weeklyFocus;

  /// No description provided for @recommendedDrill.
  ///
  /// In zh, this message translates to:
  /// **'推荐练习：{name}'**
  String recommendedDrill(String name);

  /// No description provided for @goPracticeThis.
  ///
  /// In zh, this message translates to:
  /// **'去练这个动作'**
  String get goPracticeThis;

  /// No description provided for @askCoachBtn.
  ///
  /// In zh, this message translates to:
  /// **'问 AI 教练'**
  String get askCoachBtn;

  /// No description provided for @proCompare.
  ///
  /// In zh, this message translates to:
  /// **'职业对比'**
  String get proCompare;

  /// No description provided for @scorePoster.
  ///
  /// In zh, this message translates to:
  /// **'成绩海报'**
  String get scorePoster;

  /// No description provided for @share.
  ///
  /// In zh, this message translates to:
  /// **'分享'**
  String get share;

  /// No description provided for @shootAgain.
  ///
  /// In zh, this message translates to:
  /// **'再拍一段'**
  String get shootAgain;

  /// No description provided for @backHome.
  ///
  /// In zh, this message translates to:
  /// **'返回首页'**
  String get backHome;

  /// No description provided for @skipProfileTitle.
  ///
  /// In zh, this message translates to:
  /// **'跳过档案？'**
  String get skipProfileTitle;

  /// No description provided for @skipProfileBody.
  ///
  /// In zh, this message translates to:
  /// **'你可以在「我的」里随时补填，AI 教练会更懂你。'**
  String get skipProfileBody;

  /// No description provided for @keepFilling.
  ///
  /// In zh, this message translates to:
  /// **'继续填写'**
  String get keepFilling;

  /// No description provided for @confirmSkip.
  ///
  /// In zh, this message translates to:
  /// **'确认跳过'**
  String get confirmSkip;

  /// No description provided for @skipping.
  ///
  /// In zh, this message translates to:
  /// **'跳过中…'**
  String get skipping;

  /// No description provided for @skip.
  ///
  /// In zh, this message translates to:
  /// **'跳过'**
  String get skip;

  /// No description provided for @onboardingLevelQ.
  ///
  /// In zh, this message translates to:
  /// **'你的高尔夫水平？'**
  String get onboardingLevelQ;

  /// No description provided for @onboardingGoalsQ.
  ///
  /// In zh, this message translates to:
  /// **'主要目标？（最多 {n} 个）'**
  String onboardingGoalsQ(int n);

  /// No description provided for @onboardingFreqQ.
  ///
  /// In zh, this message translates to:
  /// **'练习频率？'**
  String get onboardingFreqQ;

  /// No description provided for @previousStep.
  ///
  /// In zh, this message translates to:
  /// **'上一步'**
  String get previousStep;

  /// No description provided for @nextStep.
  ///
  /// In zh, this message translates to:
  /// **'下一步'**
  String get nextStep;

  /// No description provided for @done.
  ///
  /// In zh, this message translates to:
  /// **'完成'**
  String get done;

  /// No description provided for @monthCheckins.
  ///
  /// In zh, this message translates to:
  /// **'本月打卡 {n} 次'**
  String monthCheckins(int n);

  /// No description provided for @levelBeginnerDesc.
  ///
  /// In zh, this message translates to:
  /// **'刚接触不到 1 年'**
  String get levelBeginnerDesc;

  /// No description provided for @levelElementaryDesc.
  ///
  /// In zh, this message translates to:
  /// **'1-3 年，差点 25+'**
  String get levelElementaryDesc;

  /// No description provided for @levelIntermediateDesc.
  ///
  /// In zh, this message translates to:
  /// **'差点 10-25'**
  String get levelIntermediateDesc;

  /// No description provided for @levelAdvancedDesc.
  ///
  /// In zh, this message translates to:
  /// **'差点 10 以下'**
  String get levelAdvancedDesc;
}

class _AppLocalizationsDelegate
    extends LocalizationsDelegate<AppLocalizations> {
  const _AppLocalizationsDelegate();

  @override
  Future<AppLocalizations> load(Locale locale) {
    return SynchronousFuture<AppLocalizations>(lookupAppLocalizations(locale));
  }

  @override
  bool isSupported(Locale locale) =>
      <String>['en', 'zh'].contains(locale.languageCode);

  @override
  bool shouldReload(_AppLocalizationsDelegate old) => false;
}

AppLocalizations lookupAppLocalizations(Locale locale) {
  // Lookup logic when only language code is specified.
  switch (locale.languageCode) {
    case 'en':
      return AppLocalizationsEn();
    case 'zh':
      return AppLocalizationsZh();
  }

  throw FlutterError(
    'AppLocalizations.delegate failed to load unsupported locale "$locale". This is likely '
    'an issue with the localizations generation tool. Please file an issue '
    'on GitHub with a reproducible sample app and the gen-l10n configuration '
    'that was used.',
  );
}
