import { useRouter } from 'expo-router';
import { Pressable, ScrollView, Text, View } from 'react-native';

import { BrandMark } from '@/components/BrandMark';
import { legalStyles as styles } from '@/theme/legalStyles';
import { textStyle } from '@/theme/tokens';

const LAST_UPDATED = 'August 6, 2026';

export default function PrivacyScreen() {
  const router = useRouter();

  return (
    <ScrollView style={styles.root} contentContainerStyle={styles.rootContent} showsVerticalScrollIndicator={false}>
      <View style={styles.page}>
        <View style={styles.nav}>
          <BrandMark />
          <Pressable accessibilityRole="button" onPress={() => router.back()} style={styles.backLink}>
            <Text style={styles.backLinkText}>Back</Text>
          </Pressable>
        </View>

        <Text style={[textStyle.pageTitleMobile, styles.title]}>Privacy Policy</Text>
        <Text style={styles.updated}>Last updated: {LAST_UPDATED}</Text>

        <Text style={styles.paragraph}>
          Posted is operated by Akshat Guduru ("Posted," "we," "us"). This policy explains what
          information Posted collects, why, and how it's used. Posted is a personal finance and
          portfolio tracking application.
        </Text>

        <Text style={styles.h2}>Information we collect</Text>
        <Text style={styles.paragraph}>
          Account and login: your name and email address when you sign in with Google.
        </Text>
        <Text style={styles.paragraph}>
          Financial data: read-only account, balance, holdings, and transaction data from banks
          and brokerages you connect through Plaid, and from your Charles Schwab account through
          Schwab's OAuth connection. Posted never receives or stores your bank or brokerage
          login credentials — those connections are authorized directly with Plaid or Schwab.
        </Text>
        <Text style={styles.paragraph}>
          Phone number and SMS: if you link a phone number to text the Posted assistant, we store
          that number, a hashed verification code used only to confirm you own the number, and
          your opt-in/opt-out status. Message content you send by SMS is processed to generate a
          reply and is not shared with third parties for marketing purposes.
        </Text>
        <Text style={styles.paragraph}>
          Assistant conversations: questions you ask Posted's assistant, whether from the app or
          by SMS, are sent to Anthropic's API to generate a response grounded in your account
          data.
        </Text>

        <Text style={styles.h2}>How we use information</Text>
        <Text style={styles.paragraph}>
          To display your net worth, transactions, and portfolio; to answer questions you ask the
          assistant; to verify a phone number before enabling SMS access; and to operate and
          secure the service. We do not sell your information, and we do not use it for
          advertising.
        </Text>

        <Text style={styles.h2}>SMS-specific disclosures</Text>
        <Text style={styles.paragraph}>
          No mobile information will be shared with third parties or affiliates for marketing or
          promotional purposes. Text messaging originator opt-in data and consent will not be
          shared with any third parties, except as necessary to provide the SMS service itself
          (for example, our messaging provider, Telnyx, which delivers the texts).
        </Text>

        <Text style={styles.h2}>Data storage and security</Text>
        <Text style={styles.paragraph}>
          Access tokens for connected financial accounts are stored encrypted. Verification codes
          are stored as one-way hashes, never in plain text. You can unlink your phone number or
          disconnect a financial account at any time from Settings.
        </Text>

        <Text style={styles.h2}>Your choices</Text>
        <Text style={styles.paragraph}>
          Reply STOP to any Posted text message to opt out of SMS at any time; reply START to
          resume. You can disconnect any linked financial account or unlink your phone number
          from Settings within the app.
        </Text>

        <Text style={styles.h2}>Contact</Text>
        <Text style={styles.paragraph}>
          Questions about this policy or your data: akshat.guduru@gmail.com.
        </Text>
      </View>
    </ScrollView>
  );
}
