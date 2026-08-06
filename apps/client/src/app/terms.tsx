import { useRouter } from 'expo-router';
import { Pressable, ScrollView, Text, View } from 'react-native';

import { BrandMark } from '@/components/BrandMark';
import { legalStyles as styles } from '@/theme/legalStyles';
import { textStyle } from '@/theme/tokens';

const LAST_UPDATED = 'August 6, 2026';

export default function TermsScreen() {
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

        <Text style={[textStyle.pageTitleMobile, styles.title]}>Terms of Service</Text>
        <Text style={styles.updated}>Last updated: {LAST_UPDATED}</Text>

        <Text style={styles.paragraph}>
          These terms govern your use of Posted, a personal finance and portfolio tracking
          application operated by Akshat Guduru ("Posted," "we," "us"), an individual based in
          Florida. By using Posted, you agree to these terms.
        </Text>

        <Text style={styles.h2}>The service</Text>
        <Text style={styles.paragraph}>
          Posted lets you connect bank and brokerage accounts through Plaid and Charles Schwab to
          view a combined record of your cash and investments, and to ask an AI assistant
          questions about that data — from the app or by text message. Posted categorizes and
          summarizes financial activity for informational and planning purposes only. It is not
          financial, investment, tax, or legal advice, and you should verify important amounts
          directly with your financial institution before acting on them.
        </Text>

        <Text style={styles.h2}>Your account</Text>
        <Text style={styles.paragraph}>
          You're responsible for the accuracy of the information you connect and for keeping your
          login credentials secure. You must be able to lawfully consent to these terms to use
          Posted.
        </Text>

        <Text style={styles.h2}>SMS messaging terms</Text>
        <Text style={styles.paragraph}>
          If you link a phone number, Posted will send you a one-time verification code, and
          after verification you may text Posted questions about your account and receive
          automated replies. Message frequency varies based on your use. Message and data rates
          may apply. Reply STOP at any time to opt out, or HELP for help. Consent to receive
          texts is not a condition of using the rest of Posted.
        </Text>

        <Text style={styles.h2}>Acceptable use</Text>
        <Text style={styles.paragraph}>
          You agree not to misuse Posted — including attempting to access another user's data,
          disrupting the service, or using it for any unlawful purpose.
        </Text>

        <Text style={styles.h2}>Disclaimers</Text>
        <Text style={styles.paragraph}>
          Posted is provided "as is," without warranties of any kind. Connected-account data and
          AI-generated responses may be delayed, incomplete, or inaccurate. Posted is not a
          broker-dealer, bank, or registered investment adviser, and using it does not create
          such a relationship.
        </Text>

        <Text style={styles.h2}>Limitation of liability</Text>
        <Text style={styles.paragraph}>
          To the fullest extent permitted by law, Posted and its operator are not liable for any
          indirect, incidental, or consequential damages arising from your use of the service,
          including decisions made based on information Posted displays or the assistant
          provides.
        </Text>

        <Text style={styles.h2}>Changes</Text>
        <Text style={styles.paragraph}>
          These terms may be updated from time to time; continued use of Posted after a change
          means you accept the updated terms.
        </Text>

        <Text style={styles.h2}>Governing law</Text>
        <Text style={styles.paragraph}>
          These terms are governed by the laws of the State of Florida, without regard to its
          conflict-of-laws principles.
        </Text>

        <Text style={styles.h2}>Contact</Text>
        <Text style={styles.paragraph}>
          Questions about these terms: akshat.guduru@gmail.com.
        </Text>
      </View>
    </ScrollView>
  );
}
