/**
 * 《领翼golf 用户服务协议》静态页
 *
 * 正式对外展示稿；条款增删或权利义务有重大调整时须法务复核，
 * 并 bump `CURRENT_TERMS_VERSION`，以触发需重新确认的同意流程。
 */

import { FC } from 'react'
import { View, Text, ScrollView } from '@tarojs/components'
import { CURRENT_TERMS_VERSION } from '@/utils/storage'
import './legal.scss'

const LEGAL_META_DATE = '2026-05-13'

const TermsPage: FC = () => {
  return (
    <ScrollView scrollY className='legal legal--terms'>
      <View className='legal__inner'>
        <View className='legal__header'>
          <Text className='legal__title'>用户服务协议</Text>
          <Text className='legal__meta'>
            版本 {CURRENT_TERMS_VERSION} · 更新日期 {LEGAL_META_DATE}
          </Text>
        </View>

        <View className='legal__intro'>
          欢迎使用「领翼golf」相关产品与服务。
          「领翼golf」由北京思无界控股有限公司（下称「本公司」「我们」或「运营方」）运营。
          请您在注册登录或使用本产品前认真阅读本协议，特别是其中以加粗等形式提示与您有重大利害关系的条款。您勾选同意或开始使用本产品的，视为您已充分理解并接受本协议全部内容。
          本产品中的《隐私政策》构成本协议组成部分；与个人信息处理相关事项以《隐私政策》为准。
        </View>

        <View className='legal__section'>
          <Text className='legal__section-title'>一、服务内容</Text>
          <Text className='legal__paragraph'>
            本产品为面向高尔夫爱好者的运动辅助工具，可能包括挥杆视频的计算机视觉辅助分析、AI
            教练对话答疑、个性化训练内容与练习闭环、账户与配额管理、增值会员或服务包等，具体以您实际可用的功能为准。
          </Text>
          <Text className='legal__paragraph'>
            本产品所输出的分析评分、图示、文案与 AI 答复由算法与自动化处理生成，
            <Text className='legal__item-title'>
              仅供您在一般运动场景中参考与学习，不构成医疗诊断、康复治疗建议或由专业高尔夫教练签署的个性化现场指导结论。
            </Text>
            您应结合自身健康状况与场地条件合理使用；如出现伤病不适应及时就医。
          </Text>
        </View>

        <View className='legal__section'>
          <Text className='legal__section-title'>二、账号与实名制</Text>
          <View className='legal__list'>
            <Text className='legal__item'>
              本产品当前依托微信开放平台提供的身份能力完成账号创建与校验，您同意遵守微信平台相关规则及服务条款。
            </Text>
            <Text className='legal__item'>
              您对使用您微信身份在本产品内进行的一切操作行为负责；
              如因账号保管不善导致第三人使用而造成的损失，由您先行承担，
              我们可以在合理范围内协助您通过微信侧流程处理。
            </Text>
            <Text className='legal__item'>
              您可在「我的」等入口按指引申请注销账号；注销将导致您无法再访问历史数据，
              具体数据处理规则以《隐私政策》为准。
            </Text>
          </View>
        </View>

        <View className='legal__section'>
          <Text className='legal__section-title'>三、行为规范与内容合规</Text>
          <Text className='legal__paragraph'>
            您在使用本产品时应遵守中华人民共和国相关法律法规及微信平台规范，不得从事下列行为：
          </Text>
          <View className='legal__list'>
            <Text className='legal__item'>
              上传含有违反法律法规、公共利益或第三方合法权益的音视频、文本或截图；
            </Text>
            <Text className='legal__item'>
              发表含有淫秽、低俗、煽动歧视仇恨、虚假信息、未经许可的商业推广等内容；
            </Text>
            <Text className='legal__item'>
              未经授权破解、爬虫抓包、篡改通信、对他人账号实施攻击或套取系统接口；
            </Text>
            <Text className='legal__item'>
              绕过配额、风控或会员计费规则，或者以机器方式滥用 AI 与服务资源；
            </Text>
            <Text className='legal__item'>其他我们可能合理认定为干扰产品正常运营或不正当竞争的行为。</Text>
          </View>
          <Text className='legal__paragraph'>
            我们有权依规则采取警告、临时封禁功能、中止或终止服务、配合行政管理部门调查等措施，
            并可在法律允许的范围内向您主张因此造成的合理损失。
          </Text>
        </View>

        <View className='legal__section'>
          <Text className='legal__section-title'>四、AI 生成内容</Text>
          <Text className='legal__paragraph'>
            AI 生成的文字与建议具有不确定性与瞬时性，
            <Text className='legal__item-title'>不保证完全符合事实或无偏见</Text>
            ，亦不代表本公司对任何具体问题作出承诺或背书。
          </Text>
          <Text className='legal__paragraph'>
            如因您轻信 AI 内容而采取的球场行为、体能训练等行为导致人身或财产损失，在法律允许的最大范围内，
            我们不承担明示或暗示的保证责任，但仍然鼓励您通过本产品内客服或邮箱向我们反馈以实现产品改进。
          </Text>
        </View>

        <View className='legal__section'>
          <Text className='legal__section-title'>五、知识产权</Text>
          <Text className='legal__paragraph'>
            本产品内的软件（受法律保护部分）、图形界面设计、版面编排、预设训练素材与文字说明等，除依法属于第三方或已由您享有的内容外，其知识产权归本公司或权利人所有。
          </Text>
          <Text className='legal__paragraph'>
            您对您自行上传的原视频与基于其产生的合法独创表达享有相应权利，
            同时为使我们能够完成分析及改进服务，您在法律允许范围内向我们授予一项非独占、可转授权给技术服务分包商、仅限实现本服务的许可。
            我们不会超出《隐私政策》所述目的使用该等信息。
          </Text>
        </View>

        <View className='legal__section'>
          <Text className='legal__section-title'>六、会员、付费与发票</Text>
          <Text className='legal__paragraph'>
            我们可能提供免费功能与按需付费功能。资费标准、服务内容、计费周期（含自动续费等）以您下单时本产品内展示及微信支付订单页面为准，
            您点击开通或支付的，即与该等展示条件达成一致。
          </Text>
          <Text className='legal__paragraph'>
            微信支付及与其关联的电子发票、退票与争议处理路径，遵照腾讯支付相关产品规则与国家监管要求；
            对于已消耗的数字化服务或因您违反协议导致封号后的未使用额度，我们通常不予退费，但若法律强制性规定另行要求的除外。
          </Text>
          <Text className='legal__paragraph'>
            若您对企业采购、开票抬头等有特殊请求，可按页面指引或联系我们邮箱办理，我们将在合理核验后配合。
          </Text>
        </View>

        <View className='legal__section'>
          <Text className='legal__section-title'>七、服务的变更、中止与免责</Text>
          <View className='legal__list'>
            <Text className='legal__item'>
              为维护安全、遵从监管或不可抗力原因，我们可能短暂或长期调整、中止部分功能，
              在法律要求范围内向您公告或退回未履行完毕的预付费用。
            </Text>
            <Text className='legal__item'>
              对于非因我方故意或重大过失导致的，
              电信运营商、微信平台、云服务、电力等第三方链路故障引起的中断，
              我们在法律允许的范围内免责，但会在合理努力下尽快协助恢复。
            </Text>
          </View>
        </View>

        <View className='legal__section'>
          <Text className='legal__section-title'>八、协议的变更</Text>
          <Text className='legal__paragraph'>
            我们可能更新本协议。若更新将影响您的实质性权利，
            我们将通过在小程序登录页、弹窗、站内信或公告等您能合理注意的方式向您提示，
            必要时重新征求您对关键条款的明示同意；
            您在更新生效后仍继续使用本产品，视为接受修订后的协议。
          </Text>
        </View>

        <View className='legal__section'>
          <Text className='legal__section-title'>九、法律适用与争议解决</Text>
          <Text className='legal__paragraph'>
            本协议订立、生效、履行与解释适用中华人民共和国大陆地区法律。因本协议或使用本产品产生之争议，
            <Text className='legal__item-title'>
              双方先友好协商；协商不成时，提交本公司住所地有管辖权的人民法院诉讼解决。
            </Text>
          </Text>
        </View>

        <View className='legal__section'>
          <Text className='legal__section-title'>十、联系我们</Text>
          <Text className='legal__paragraph'>公司名称：北京思无界控股有限公司</Text>
          <Text className='legal__paragraph'>联系邮箱：easongolf@outlook.com</Text>
          <Text className='legal__paragraph'>
            您也可以通过小程序内「意见反馈」与我们联系；我们将在核验身份后对合理问询予以答复。
          </Text>
        </View>

        <Text className='legal__footer'>
          {`本协议解释权在法律允许范围内由北京思无界控股有限公司享有。\n`}
          如对条款有疑问，请以本页所载版本与日期的文本为准：
          {LEGAL_META_DATE}。
        </Text>
      </View>
    </ScrollView>
  )
}

export default TermsPage
