// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for English (`en`).
class AppLocalizationsEn extends AppLocalizations {
  AppLocalizationsEn([String locale = 'en']) : super(locale);

  @override
  String get appName => 'Lingyi Golf';

  @override
  String get appNameShort => 'Lingyi';

  @override
  String get tagline => 'Your on-demand AI golf coach';

  @override
  String get language => 'Language';

  @override
  String get languageSystem => 'System default';

  @override
  String get languageZh => '简体中文';

  @override
  String get languageEn => 'English';

  @override
  String get tabHome => 'Home';

  @override
  String get tabCoach => 'AI Coach';

  @override
  String get tabTraining => 'Training';

  @override
  String get tabProfile => 'Me';

  @override
  String get login => 'Sign in';

  @override
  String get goLogin => 'Sign in';

  @override
  String get loginRequiredHint =>
      'Sign in to analyze swings and chat with the AI coach.';

  @override
  String get agreeFirst => 'Please agree to the terms first';

  @override
  String get agreeReadPrefix => 'I have read and agree to the';

  @override
  String get userAgreement => 'Terms of Service';

  @override
  String get privacyPolicy => 'Privacy Policy';

  @override
  String get andWord => 'and';

  @override
  String get browseAsGuest => 'Skip for now';

  @override
  String get signingIn => 'Signing in…';

  @override
  String get wechatLogin => 'Continue with WeChat';

  @override
  String get appleLoginHint =>
      'Use Sign in with Apple. WeChat is not required.';

  @override
  String get appleDeviceRequired =>
      'Sign in with Apple is required on this device';

  @override
  String get inviteOptional => 'Have an invite code? (optional)';

  @override
  String get inviteHint => 'Enter 8-character code';

  @override
  String get inviteBonus =>
      'Invite codes give you and your friend +1 analysis this month';

  @override
  String get featureSwing => 'AI swing analysis in about 30 seconds';

  @override
  String get featureCoach => '24/7 AI coach Q&A';

  @override
  String get featurePlan => 'Personalized practice plans';

  @override
  String get welcomeUse => 'Welcome';

  @override
  String get guestSubtitle1 => 'Explore the product first';

  @override
  String get guestSubtitle2 => 'Then sign in when you are ready';

  @override
  String get guestLegalHint =>
      'Swing analysis and AI chat require an account. You can view a sample report and policies below.';

  @override
  String get loginToAnalyze => 'Sign in to start analyzing';

  @override
  String get productOffers => 'What you get';

  @override
  String get guestFeatSwing => 'AI swing analysis from a short video';

  @override
  String get guestFeatCoach =>
      'AI coach answers (generated, for reference only)';

  @override
  String get guestFeatPlan => 'Practice plans and check-ins from your analysis';

  @override
  String get sampleReportTitle => 'See a sample report';

  @override
  String get sampleReportSubGuest => 'No sign-in · Does not use your quota';

  @override
  String get sampleReportSubUser => 'See what AI can do · Does not use quota';

  @override
  String get coachIntroTitle => 'AI Coach';

  @override
  String get coachIntroSub => 'Learn what it can do; chatting requires sign-in';

  @override
  String helloGolfer(String name) {
    return 'Hi, $name 👋';
  }

  @override
  String get golferFallback => 'golfer';

  @override
  String get heroCta => 'Film a swing and get an AI report in about 30 seconds';

  @override
  String get uploadNewSwing => '+ Upload a new swing';

  @override
  String get startFirstAnalysis => 'Start your first analysis';

  @override
  String get quotaMemberUnlimited => 'Member · Unlimited swing analyses';

  @override
  String quotaMonthRemaining(int remaining, int total) {
    return 'Analyses left this month: $remaining/$total';
  }

  @override
  String get statTotalAnalyses => 'Analyses';

  @override
  String get statBestScore => 'Best score';

  @override
  String get statStreak => 'Streak';

  @override
  String get askCoach => 'Ask the AI coach';

  @override
  String get memberUnlimited => 'Unlimited (member)';

  @override
  String chatRemainingToday(int n) {
    return '$n chats left today';
  }

  @override
  String get recentAnalyses => 'Recent analyses';

  @override
  String get viewAll => 'See all ›';

  @override
  String get noAnalysesYet => 'No analyses yet. Upload your first swing.';

  @override
  String get statusFailed => 'Failed';

  @override
  String get statusAnalyzing => 'Analyzing';

  @override
  String get quotaExhaustedTitle => 'Monthly analysis quota used up';

  @override
  String get quotaExhaustedBody =>
      'Your free analyses for this month are used up. Try again next month, or wait for in-app membership (Apple IAP).';

  @override
  String get gotIt => 'OK';

  @override
  String get viewBenefits => 'See membership benefits';

  @override
  String todayAt(String time) {
    return 'Today $time';
  }

  @override
  String get scoreUnit => ' pts';

  @override
  String get latestShot => 'Latest swing';

  @override
  String get analysisDone => 'Analysis complete';

  @override
  String get settings => 'Settings';

  @override
  String get sectionExperience => 'Experience';

  @override
  String get replayCaptureGuide => 'Show capture guide again';

  @override
  String get guideResetToast =>
      'Reset. The capture guide will show on your next analysis.';

  @override
  String get clearCache => 'Clear local cache';

  @override
  String get clearCacheBody =>
      'This clears local sign-in and settings. You will need to sign in again.';

  @override
  String get cancel => 'Cancel';

  @override
  String get confirmClear => 'Clear';

  @override
  String get sectionLegal => 'Legal';

  @override
  String get aboutApp => 'About Lingyi Golf';

  @override
  String get deleteAccount => 'Delete account';

  @override
  String get logout => 'Sign out';

  @override
  String get logoutConfirm => 'Sign out?';

  @override
  String get prompt => 'Notice';

  @override
  String get membershipCenter => 'Membership';

  @override
  String get freeUser => 'Free plan';

  @override
  String get memberThanks =>
      'Thanks for supporting Lingyi. Enjoy full member access.';

  @override
  String get membershipFreeHint =>
      'This version includes a free quota. Paid membership, if offered later, will use Apple In-App Purchase.';

  @override
  String get membershipNoIap =>
      'Paid membership is not sold in this app build. Keep using your free analysis and chat quota. Future subscriptions will use Apple In-App Purchase only.';

  @override
  String get memberYearly => 'Annual member';

  @override
  String get memberMonthly => 'Monthly member';

  @override
  String get memberGeneric => 'Member';

  @override
  String memberRemainingDays(String label, int days) {
    return '$label · $days days left';
  }

  @override
  String get benefitSwing => 'Swing video analysis';

  @override
  String get benefitCoach => 'AI coach chat';

  @override
  String get benefitPlan => 'This week\'s practice plan';

  @override
  String get benefitCurve => 'Progress curve';

  @override
  String get benefitCompare => 'Report comparison';

  @override
  String get tierLimitedMonth => 'Limited per month';

  @override
  String get tierLimitedDay => 'Limited per day';

  @override
  String get tierViewOnly => 'View only';

  @override
  String get tierBasic => 'Basic';

  @override
  String get tierUnlimited => 'Unlimited';

  @override
  String get tierFullPlan => 'Full personalized plan';

  @override
  String get tierFullHistory => 'Full history & chart';

  @override
  String get tierSideBySide => 'Side-by-side';

  @override
  String get helpCenter => 'Help';

  @override
  String get faqShootQ => 'How do I film a good swing video?';

  @override
  String get faqShootA =>
      'Use good light, keep the phone steady (landscape or portrait), and capture address through finish. Face-on or down-the-line both work. Aim for 2–30 seconds.';

  @override
  String get faqHowLongQ => 'How long does analysis take?';

  @override
  String get faqHowLongA =>
      'After upload, reports usually finish within about 30 seconds. Weak networks can take longer.';

  @override
  String get faqQuotaQ => 'What if I run out of analyses?';

  @override
  String get faqQuotaA =>
      'The free quota resets each month. This app build does not sell membership; that will use Apple In-App Purchase if added later.';

  @override
  String get faqCoachQ => 'What can the AI coach answer?';

  @override
  String get faqCoachA =>
      'Swing technique, practice plans, rules questions, and equipment — golf topics in general.';

  @override
  String get faqDataQ => 'Is my data safe?';

  @override
  String get faqDataA =>
      'Swing video and account data are processed on our cloud. Conversational generation may use models such as DeepSeek. You can delete data or your account anytime in Me.';

  @override
  String get aiConsentTitle => 'AI data processing';

  @override
  String get aiConsentSwing =>
      'We will upload the swing video you chose and related parameters (club, camera view) to generate a report.';

  @override
  String get aiConsentChat =>
      'We will send your message and needed context to generate an AI coach reply.';

  @override
  String get aiConsentReceivers => 'Recipients:';

  @override
  String get aiConsentOurCloud =>
      'Lingyi Golf cloud (Beijing Siwujie Holdings Co., Ltd.)';

  @override
  String get aiConsentProvider =>
      'LLM providers such as DeepSeek (for chat / generated copy)';

  @override
  String get aiConsentPurpose =>
      'Purpose: swing analysis or AI Q&A in this product only. We do not sell your personal information. Identifiable content is not used for unrelated model training unless you separately agree.\n\nSee the Privacy Policy for details. Continue?';

  @override
  String get disagree => 'Don’t agree';

  @override
  String get agreeContinue => 'Agree and continue';

  @override
  String get coachWelcome =>
      'Hi — I’m Lingyi Golf’s AI coach. Ask about swing technique, practice, or golf knowledge anytime.';

  @override
  String get chatQuotaExhausted => 'Daily chat quota used up';

  @override
  String get rateLimited => 'Too fast. Please wait a moment.';

  @override
  String get clearChatTitle => 'Clear this chat?';

  @override
  String get clearChatStreaming =>
      'The AI is still replying. Clearing will stop it immediately.';

  @override
  String get clearChatBody =>
      'This deletes the current session. The next message starts a new chat.';

  @override
  String get clearAction => 'Clear';

  @override
  String get loginToChat => 'Sign in to chat with the AI coach';

  @override
  String get connectingCoach => 'Connecting to the AI coach…';

  @override
  String get loadFailed => 'Couldn’t load';

  @override
  String get reload => 'Retry';

  @override
  String get reportBasedChat => 'Chat about this report';

  @override
  String get viewOriginalReport => 'Open report ›';

  @override
  String get tryThese => 'Try asking:';

  @override
  String get needsAnalysis => 'Needs analysis';

  @override
  String get needUploadFirstTitle => 'Upload a swing first';

  @override
  String get needUploadFirstBody =>
      'This question needs your swing analysis. Go to Home → start an analysis first.';

  @override
  String get copied => 'Copied';

  @override
  String get chatUsedUp => 'Used up for today';

  @override
  String chatRemainFrac(int remaining, int total) {
    return '$remaining/$total left today';
  }

  @override
  String get chatUsedUpHint => 'Daily chat quota used up';

  @override
  String get aiReplying => 'The AI is still replying…';

  @override
  String get askCoachHint => 'Ask the AI coach…';

  @override
  String get me => 'Me';

  @override
  String get tapRetry => '↻ Tap to retry';

  @override
  String get training => 'Training';

  @override
  String get loginToSeePlan => 'Sign in to see your practice plan';

  @override
  String get loginToSeeCalendar =>
      'The check-in calendar and progress curve appear after you sign in';

  @override
  String get checkinFailed => 'Check-in failed. Try again later.';

  @override
  String get checkinOk => 'Checked in!';

  @override
  String checkinStreak(int n) {
    return 'Checked in! $n-day streak';
  }

  @override
  String get checkinSuggestReshoot =>
      'Film another swing from the same camera view to compare.';

  @override
  String get later => 'Later';

  @override
  String get goCapture => 'Film now';

  @override
  String get practiceCalendar => 'Practice calendar';

  @override
  String get progressCurve => 'Progress';

  @override
  String get last90 => 'Last 90 days';

  @override
  String get allTime => 'All';

  @override
  String get progressHint =>
      'Score trends appear after you complete analyses. Members see a fuller curve.';

  @override
  String get noPlanTitle => 'No practice plan yet';

  @override
  String get noPlanBody =>
      'Upload a swing video first. AI will build this week’s plan from your report.';

  @override
  String get goUpload => 'Upload a video';

  @override
  String taskCount(int n) {
    return '$n tasks';
  }

  @override
  String get loadFailedRetry => 'Couldn’t load. Please retry.';

  @override
  String get weekPlan => 'This week';

  @override
  String get completed => 'Done';

  @override
  String get pending => 'To do';

  @override
  String streakDays(int n) {
    return '$n-day streak';
  }

  @override
  String get submitting => 'Saving…';

  @override
  String get completeCheckin => 'Check in';

  @override
  String get profileSyncHint => 'Sign in to sync your profile and analyses';

  @override
  String get myReports => 'My reports';

  @override
  String get coachChat => 'AI coach chat';

  @override
  String get myClubs => 'My clubs';

  @override
  String get lessons => 'Lessons';

  @override
  String get proLibrary => 'Pro comparison';

  @override
  String get meetup => 'Tee times';

  @override
  String get deletionPending =>
      'Account deletion is scheduled. Tap to view or cancel.';

  @override
  String get edit => 'Edit';

  @override
  String get golfProfile => 'Golf profile';

  @override
  String get modify => 'Edit';

  @override
  String get level => 'Level';

  @override
  String get goals => 'Goals';

  @override
  String get practiceFreq => 'Practice frequency';

  @override
  String get notSet => 'Not set';

  @override
  String get statAnalyses => 'Analyses';

  @override
  String get statCheckin => 'Streak';

  @override
  String get statHighScore => 'Best score';

  @override
  String get consentWelcome => 'Welcome to Lingyi Golf';

  @override
  String get consentBefore => 'Before you start';

  @override
  String get consentIntro =>
      'We take your privacy seriously. To use this product we need:';

  @override
  String get consentBulletApple =>
      'Apple account identifier: for Sign in with Apple.';

  @override
  String get consentBulletVideo =>
      'Swing videos: uploaded only after you choose them and agree, for AI analysis on our cloud.';

  @override
  String get consentBulletChat =>
      'Chat text: used for AI coaching; replies may be generated via models such as DeepSeek.';

  @override
  String get consentStorage =>
      'Our cloud processes your data; chat generation may use LLM providers. You can view, delete, or close your account anytime in Me.';

  @override
  String get consentDisagreeExit =>
      'If you don’t agree, please exit. You can return later and agree.';

  @override
  String get notNow => 'Not now';

  @override
  String get disagreeCannotUse => 'You need to agree to use this product';

  @override
  String get withWord => 'and';

  @override
  String get colBenefit => 'Benefit';

  @override
  String get colFree => 'Free';

  @override
  String get listSep => ', ';

  @override
  String get weekdayMon => 'Mon';

  @override
  String get weekdayTue => 'Tue';

  @override
  String get weekdayWed => 'Wed';

  @override
  String get weekdayThu => 'Thu';

  @override
  String get weekdayFri => 'Fri';

  @override
  String get weekdaySat => 'Sat';

  @override
  String get weekdaySun => 'Sun';

  @override
  String dateWeekday(String md, String wd) {
    return '$md $wd';
  }

  @override
  String get levelBeginner => 'Beginner';

  @override
  String get levelElementary => 'Elementary';

  @override
  String get levelIntermediate => 'Intermediate';

  @override
  String get levelAdvanced => 'Advanced';

  @override
  String get goalDistance => 'More distance';

  @override
  String get goalAccuracy => 'Better accuracy';

  @override
  String get goalShortGame => 'Short game';

  @override
  String get goalPutting => 'Putting';

  @override
  String get goalConsistency => 'Consistency';

  @override
  String get freqOccasional => 'Occasionally';

  @override
  String get freqOnce => 'Once a week';

  @override
  String get freqFrequent => '2–3 times a week';

  @override
  String get freqDaily => 'Almost daily';

  @override
  String get captureTitle => 'Swing analysis';

  @override
  String get captureOnlyMp4Mov => 'Only mp4 / mov videos are supported';

  @override
  String get captureTooLarge => 'Video must be 100MB or smaller';

  @override
  String captureTooShort(int n) {
    return 'Video is too short (need ≥ ${n}s)';
  }

  @override
  String captureTooLong(int n) {
    return 'Video is too long (need ≤ ${n}s)';
  }

  @override
  String capturePickFailed(String error) {
    return 'Couldn’t pick video: $error';
  }

  @override
  String get captureNeedVideo => 'Film or choose a swing video first';

  @override
  String captureLimits(int min, int max, int mb, String ext) {
    return '$min–$max s · ≤ ${mb}MB · $ext';
  }

  @override
  String get captureNextParams => 'Next: choose parameters';

  @override
  String get captureTrySample => 'Try a sample report first';

  @override
  String get captureCenterSubject => 'Keep the player centered in frame';

  @override
  String get captureTipFraming =>
      'Place the player in the center; head to feet fully visible';

  @override
  String get captureTipLength =>
      'Record at least 2 seconds (3–5s is better), one full swing';

  @override
  String get captureTipLight =>
      'Prefer natural light; avoid strong backlight and heavy shake';

  @override
  String get capturePrompt => 'Film or pick a swing video (2–30 seconds)';

  @override
  String captureSelected(String duration, String size) {
    return 'Selected · ${duration}s · ${size}MB';
  }

  @override
  String get record => 'Record';

  @override
  String get album => 'Photos';

  @override
  String get paramsTitle => 'Analysis settings';

  @override
  String get paramsMode => 'Mode';

  @override
  String get paramsModeHint =>
      'Putting/chipping need a server flag. If create fails, switch back to full swing.';

  @override
  String get paramsClub => 'Club';

  @override
  String get paramsCamera => 'Camera view';

  @override
  String get paramsUploading => 'Uploading…';

  @override
  String get paramsDetecting => 'Detecting swing segments…';

  @override
  String get paramsCreating => 'Creating analysis…';

  @override
  String get paramsStartFailed => 'Couldn’t start analysis';

  @override
  String get paramsProcessing => 'Working…';

  @override
  String get paramsStart => 'Start analysis';

  @override
  String get modeFullSwing => 'Full swing';

  @override
  String get modeFullSwingSub => 'Irons / driver';

  @override
  String get modePutting => 'Putting';

  @override
  String get modePuttingSub => 'On the green';

  @override
  String get modeChipping => 'Chipping';

  @override
  String get modeChippingSub => 'Chip / pitch';

  @override
  String get waitingReceived => 'Video received';

  @override
  String get waitingPose => 'Detecting pose';

  @override
  String get waitingSwing => 'Analyzing the swing';

  @override
  String get waitingDiagnose => 'Writing diagnosis';

  @override
  String get waitingRender => 'Rendering the report';

  @override
  String get waitingDone => 'Analysis complete';

  @override
  String get waitingInProgress => 'AI is analyzing your swing';

  @override
  String get waitingOpening => 'Opening your report…';

  @override
  String waitingEtaSeconds(int n) {
    return 'About ${n}s remaining';
  }

  @override
  String get waitingEtaSoon => 'Less than 30s remaining';

  @override
  String get waitingSlowHint =>
      'This is taking longer than usual. Stay here, or check My reports later.';

  @override
  String get waitingSlowTitle => '⏳ Taking longer than expected';

  @override
  String get waitingSlowBody =>
      'The job is still running. You’ll find the report in My reports when it’s done, or go Home and come back later.';

  @override
  String get waitingBackHome => 'Go Home for now';

  @override
  String waitingDidYouKnow(String category) {
    return '$category  ·  Did you know?';
  }

  @override
  String get waitingFailed => 'Analysis failed';

  @override
  String get waitingReshoot => 'Film again';

  @override
  String get waitingGoHome => 'Go Home';

  @override
  String get reportLoading => 'Loading report…';

  @override
  String get reportLoadFailed => 'Couldn’t load the report';

  @override
  String get retry => 'Retry';

  @override
  String get scoreGuideLink => 'Scoring guide ›';

  @override
  String get sampleReportBanner =>
      'This is a demo report with real-style findings. It does not use your quota.';

  @override
  String get clipOriginal => 'Original';

  @override
  String get clipSkeleton => 'Skeleton';

  @override
  String get playbackSpeed => 'Speed';

  @override
  String get vsLastSameType => 'vs last same-type swing';

  @override
  String get highlightsThisSwing => 'Highlights';

  @override
  String get filmingTips => 'Filming tips';

  @override
  String get sixDimScores => 'Six-dimension scores';

  @override
  String get tapPhaseToJump => 'Tap a phase to jump in the video';

  @override
  String get mostNeedImprove => 'Needs work';

  @override
  String get otherIssues => 'Other issues';

  @override
  String get issueDiagnosis => 'Diagnosis';

  @override
  String get weeklyFocus => 'This week’s focus';

  @override
  String recommendedDrill(String name) {
    return 'Suggested drill: $name';
  }

  @override
  String get goPracticeThis => 'Practice this';

  @override
  String get askCoachBtn => 'Ask AI coach';

  @override
  String get proCompare => 'Pro compare';

  @override
  String get scorePoster => 'Score card';

  @override
  String get share => 'Share';

  @override
  String get shootAgain => 'Film another';

  @override
  String get backHome => 'Back to Home';

  @override
  String get skipProfileTitle => 'Skip your profile?';

  @override
  String get skipProfileBody =>
      'You can fill this in later under Me. The AI coach will use it when you do.';

  @override
  String get keepFilling => 'Keep going';

  @override
  String get confirmSkip => 'Skip';

  @override
  String get skipping => 'Skipping…';

  @override
  String get skip => 'Skip';

  @override
  String get onboardingLevelQ => 'What’s your golf level?';

  @override
  String onboardingGoalsQ(int n) {
    return 'Main goals? (up to $n)';
  }

  @override
  String get onboardingFreqQ => 'How often do you practice?';

  @override
  String get previousStep => 'Back';

  @override
  String get nextStep => 'Next';

  @override
  String get done => 'Done';

  @override
  String monthCheckins(int n) {
    return '$n check-ins this month';
  }

  @override
  String get levelBeginnerDesc => 'New to golf, under 1 year';

  @override
  String get levelElementaryDesc => '1–3 years, handicap 25+';

  @override
  String get levelIntermediateDesc => 'Handicap 10–25';

  @override
  String get levelAdvancedDesc => 'Handicap under 10';
}
