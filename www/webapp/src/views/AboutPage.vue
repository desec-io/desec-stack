<template>
  <div>
    <v-card outline tile class="pa-md-12 pa-8 elevation-4" style="overflow: hidden">
      <div class="d-md-block logo-bg pt-4">
        <v-img
                  :src="require('../assets/logo.notext.svg')"
                  alt="deSEC Logo"
                  contain
                  height="90%"
          ></v-img>
      </div>
      <v-container class="pa-0">
        <v-row align="center">
          <v-col class="col-md-6 col-12 py-8 triangle-fg">
            <h1 class="text-h4 font-weight-bold">About Us</h1>
            <h3 class="subheading mt-2 py-8 font-weight-regular">
              <p>
                Our services are operated by deSEC e.V., a registered non-profit organization in Berlin, Germany.
              </p>
              <p>
                As a charity, all operations abide by our statutes which define guidelines of all operations.
                For details regarding our statutes, please refer to the legally binding version (German) below.
              </p>
            </h3>
          </v-col>
        </v-row>
      </v-container>
    </v-card>
    <v-container fluid class="grey lighten-4">
      <v-container>
        <v-row class="pt-8">
          <v-col class="text-center">
            <h1>deSEC in a Nutshell</h1>
          </v-col>
        </v-row>
        <v-row class="pb-8">
          <v-col class="col-12 col-sm-6 d-flex" v-for="p in purposes" :key="p.title">
            <v-card>
              <v-card-title>{{ p.title }}</v-card-title>
              <v-card-text>{{ p.text }}</v-card-text>
            </v-card>
          </v-col>
        </v-row>
      </v-container>
    </v-container>
    <v-container class="pt-8" id="satzung">
      <h2>Satzung / Statutes</h2>
      <p>vom 17. September 2019.</p>

      <h3 id="name-und-sitz">§ 1 Name und Sitz</h3>
      <p>Der Verein führt den Namen: deSEC</p>
      <p>Er soll in das Vereinsregister eingetragen werden und trägt dann den Zusatz “e.V.”. Der Sitz des Vereins ist Berlin.</p>
      <h3 id="geschäftsjahr">§ 2 Geschäftsjahr</h3>
      <p>Geschäftsjahr ist das Kalenderjahr.</p>
      <h3 id="zweck-des-vereins">§ 3 Zweck des Vereins</h3>
      <ol type="1">
      <li>Der Verein verfolgt ausschließlich und unmittelbar gemeinnützige Zwecke im Sinne des Abschnitts “Steuerbegünstigte Zwecke” der Abgabenordnung.</li>
      <li>Zweck des Vereins ist die Förderung
      <ol type="a">
      <li>von Verbraucherberatung und Verbraucherschutz,</li>
      <li>von Wissenschaft und Forschung sowie</li>
      <li>der Volks- und Berufsbildung.</li>
      </ol></li>
      <li>Den Satzungszweck nach Absatz 2 lit. a) verfolgt der Verein durch Maßnahmen zur Verbreitung von Sicherheitsmaßnahmen zum Schutze von Verbraucherinnen und Verbrauchern im Internet, insbesondere durch Verschlüsselung und Sicherstellung der Unverfälschtheit (Authentizität) der über das Internet übertragenen Daten. Maßnahmen in diesem Sinne sind insbesondere
      <ol type="a">
      <li>die Entwicklung und der Betrieb von öffentlich zugänglichen Internetdiensten, die einen technischen Beitrag zur Verbesserung der Internetsicherheit leisten, beispielsweise von sicheren Namensauflösungsdiensten (DNS) oder Verfahren zum sicheren Austausch kryptografischer Schlüssel für Ende-zu-Ende-Kommunikationssicherheit,</li>
      <li>die Information und Aufklärung von Bürgerinnen und Bürgern über Möglichkeiten zur technischen Durchsetzung ihrer Privatsphäreinteressen, insbesondere durch Aufbau von Internet-Informationsangeboten, durch Herstellung und Vertrieb von Schriften und durch Organisation und Durchführung von Informationsveranstaltungen;</li>
      <li>die Vernetzung von Akteurinnen und Akteuren, die sich für die praktische Verbesserung der Internetsicherheit engagieren, durch Arbeitstreffen, Tagungen und andere Formen des Austauschs von Expertise.</li>
      </ol></li>
      <li>Den Satzungszweck nach Absatz 2 lit. b) bzw. lit c) verfolgt der Verein im Hinblick auf die Erforschung der Voraussetzungen sicherer Kommunikation, die sich bei der Verfolgung des Zwecks nach Absatz 2 lit. a) stellen,
      <ol type="a">
      <li>durch die Organisation und Durchführung wissenschaftlicher Veranstaltungen (Tagungen, Symposien etc.);</li>
      <li>durch eigene Erforschung von Sicherheitslücken und verwandten Forschungsfeldern sowie deren öffentliche Kommunikation, beispielsweise durch Publikationen und Vorträge;</li>
      <li>durch die Vergabe von Forschungsaufträgen an Hilfspersonen im Sinne des § 57 Absatz 1 Satz 2 der Abgabenordnung;</li>
      <li>durch die Ausbildung und Anleitung von Studierenden sowie jungen Wissenschaftlerinnen und Wissenschaftlern. Forschungsergebnisse, die mit Mitteln des Vereins erzielt wurden, veröffentlicht der Verein zeitnah. Die Veröffentlichung erfolgt spätestens nach 12 Monaten, sofern die Mitgliederversammlung nicht im Einzelfall etwas anderes beschließt.</li>
      </ol></li>
      <li>Angebote des Vereins erfolgen in der Regel unentgeltlich oder spendenfinanziert und grundsätzlich ohne Gewinnerzielungsabsicht. Der Verein darf zur Kostendeckung Entgelte erheben.</li>
      </ol>
      <h3 id="selbstlose-tätigkeit">§ 4 Selbstlose Tätigkeit</h3>
      <p>Der Verein ist selbstlos tätig; er verfolgt nicht in erster Linie eigenwirtschaftliche Zwecke.</p>
      <h3 id="mittelverwendung">§ 5 Mittelverwendung</h3>
      <ol type="1">
      <li>Mittel des Vereins dürfen nur für die satzungsmäßigen Zwecke verwendet werden. Die Mitglieder erhalten keine Zuwendungen aus Mitteln des Vereins.</li>
      <li>Zahlungen an Mitglieder sind nur gestattet, soweit dies unmittelbar dem Vereinszweck dient, etwa durch die Zahlung von marktüblichen Honoraren für Leistungen oder durch den Ersatz von Aufwendungen für Zwecke des Vereins. Der Verein kann Mitarbeiterinnen und Mitarbeiter beschäftigen.</li>
      </ol>
      <h3 id="verbot-von-begünstigungen">§ 6 Verbot von Begünstigungen</h3>
      <p>Es darf keine Person durch Ausgaben, die dem Zweck des Vereins fremd sind, oder durch unverhältnismäßig hohe Vergütungen begünstigt werden.</p>
      <h3 id="erwerb-der-mitgliedschaft">§ 7 Erwerb der Mitgliedschaft</h3>
      <ol type="1">
      <li>Nur natürliche Personen können Vereinsmitglieder werden.</li>
      <li>Der Aufnahmeantrag ist in Textform unter Angabe einer postalischen und einer eMail-Adresse zu stellen.</li>
      <li>Über den Aufnahmeantrag entscheidet der Vorstand.</li>
      <li>Neben den ordentlichen Mitgliedern kann der Verein natürliche oder juristische Personen als Fördermitglieder aufnehmen, die sich bereiterklären, die Zwecke des Vereins durch regelmäßige Beiträge zu unterstützen. Fördermitglieder sind keine Mitglieder des Vereins im Sinne des BGB oder dieser Satzung. Über ihre Aufnahme entscheidet der Vorstand; der Austritt ist schriftlich mit einer Frist von einem Monat zum Ende des Geschäftsjahres gegenüber einem Vorstandsmitglied zu erklären.</li>
      </ol>
      <h3 id="beendigung-der-mitgliedschaft">§ 8 Beendigung der Mitgliedschaft</h3>
      <ol type="1">
      <li>Die Mitgliedschaft endet durch Austritt, Ausschluss, Tod oder Auflösung der juristischen Person.</li>
      <li>Der Austritt erfolgt durch Erklärung in Textform gegenüber einem vertretungsberechtigten Vorstandsmitglied. Er muss mit einer Frist von einem Monat jeweils zum Ende des Geschäftsjahres erklärt werden.</li>
      <li>Ein Ausschluss kann nur aus wichtigem Grund erfolgen. Wichtige Gründe sind insbesondere ein die Vereinsziele schädigendes Verhalten, die Verletzung satzungsmäßiger Pflichten oder die schuldhafte Nichtzahlung des Vereinsbeitrags, etwa wenn ein Mitglied mit seinem Beitrag in Höhe von mindestens einem Jahresbeitrag für die Dauer von mindestens drei Monaten im Verzug ist und diesen Rückstand auch nach Mahnung in Textform nicht binnen eines Monats nach Zugang zurückführt. Über den Ausschluss entscheidet der Vorstand. Dem Mitglied bleibt die Überprüfung der Maßnahme durch Anrufung der ordentlichen Gerichte vorbehalten. Die Anrufung eines ordentlichen Gerichts hat aufschiebende Wirkung bis zur Rechtskraft der gerichtlichen Entscheidung.</li>
      <li>Bei Beendigung der Mitgliedschaft, gleich aus welchem Grund, erlöschen alle Ansprüche aus dem Mitgliedsverhältnis. Eine Rückgewähr von Beiträgen, Spenden oder sonstigen Unterstützungsleistungen ist ausgeschlossen. Der Anspruch des Vereins auf rückständige Beitragsforderungen bleibt hiervon unberührt.</li>
      <li>Die vorstehenden Absätze gelten für Fördermitglieder entsprechend.</li>
      </ol>
      <h3 id="beiträge">§ 9 Beiträge</h3>
      <ol type="1">
      <li>Von den Mitgliedern werden Beiträge erhoben. Die Höhe der Beiträge und deren Fälligkeit bestimmt die Mitgliederversammlung.</li>
      <li>Für die Fördermitglieder legt der Vorstand einstimmig einen Mindestbeitrag sowie dessen Fälligkeit fest. Die Fördermitglieder leisten mindestens diesen Beitrag und darüber hinaus diejenigen Beiträge, zu denen sie sich jeweils bereiterklärt haben.</li>
      </ol>
      <h3 id="organe-des-vereins">§ 10 Organe des Vereins</h3>
      <p>Organe des Vereins sind</p>
      <ol type="1">
      <li>die Mitgliederversammlung</li>
      <li>der Vorstand.</li>
      </ol>
      <h3 id="mitgliederversammlung">§ 11 Mitgliederversammlung</h3>
      <ol type="1">
      <li>Die Mitgliederversammlung ist das oberste Vereinsorgan.</li>
      <li>Zu den Aufgaben der Mitgliederversammlung gehören insbesondere
      <ol type="a">
      <li>die Wahl und Abwahl des Vorstands;</li>
      <li>die Entlastung des Vorstands;</li>
      <li>die Entgegennahme der Berichte des Vorstandes;</li>
      <li>die Wahl der Kassenprüferin oder des Kassenprüfers;</li>
      <li>die Festsetzung von Beiträgen und deren Fälligkeit;</li>
      <li>die Beschlussfassung über die Änderung der Satzung, die Auflösung des Vereins sowie weitere Aufgaben, soweit sich diese aus dieser Satzung oder dem Gesetz ergeben.</li>
      </ol></li>
      <li>Der Vorstand ist zur Einberufung einer Mitgliederversammlung zumindest alle zwei Jahre verpflichtet; außerdem hat er eine außerordentliche Mitgliederversammlung einzuberufen, wenn mindestens ein Drittel der Mitglieder dies schriftlich unter Angabe von Gründen verlangt.</li>
      <li>Die Mitgliederversammlung wird vom Vorstand unter Einhaltung einer Frist von zwei Wochen in Textform unter Angabe der Tagesordnung einberufen. Die Frist beginnt mit dem auf die Absendung der Einladung folgenden Tag. Das Einladungsschreiben gilt als den Mitgliedern zugegangen, zwei Tage nachdem es an die letzte dem Verein bekannt gegebene postalische oder eMail-Anschrift gerichtet wurde.</li>
      <li>Die Tagesordnung ist zu ergänzen, wenn dies ein Mitglied bis spätestens eine Woche vor dem angesetzten Termin in Textform bei einem vertretungsberechtigten Vorstandsmitglied beantragt. Die Ergänzung ist zu Beginn der Versammlung bekanntzumachen.</li>
      <li>Anträge über die Abwahl des Vorstands, über die Änderung der Satzung und über die Auflösung des Vereins, die den Mitgliedern nicht bereits mit der Einladung zur Mitgliederversammlung zugegangen sind, können erst auf der nächsten Mitgliederversammlung beschlossen werden.</li>
      <li>Die Mitgliederversammlung ist ohne Rücksicht auf die Zahl der erschienenen Mitglieder beschlussfähig.</li>
      </ol>
      <h3 id="ablauf-der-mitgliederversammlung">§ 12 Ablauf der Mitgliederversammlung</h3>
      <ol type="1">
      <li>Die Mitgliederversammlung wird von der oder dem Vorsitzenden, im Falle der Verhinderung von einem oder einer Beisitzenden geleitet.</li>
      <li>Zu Beginn der Mitgliederversammlung ist eine Protokollführerin oder ein Protokollführer zu wählen.</li>
      <li>Bei Wahlen und Abstimmungen hat jedes Mitglied eine Stimme. Das Stimmrecht kann nur ausgeübt werden
      <ol type="a">
      <li>persönlich;</li>
      <li>für ein anderes Mitglied unter Vorlage einer schriftlichen Vollmacht oder</li>
      <li>für ein anderes Mitglied, wenn das vertretene Mitglied dem Vertreter durch Erklärung gegenüber einem vertretungsberechtigten Vorstandsmitglied in Textform spätestens am Tag vor der Mitgliederversammlung Vollmacht erteilt hat.</li>
      </ol></li>
      <li>Bei Wahlen und Abstimmungen entscheidet die einfache Mehrheit der abgegebenen Stimmen. Stimmenthaltungen und ungültige Stimmen bleiben außer Betracht.</li>
      <li>Satzungsänderungen und die Auflösung des Vereins können nur mit einer Mehrheit von zwei Dritteln der anwesenden Mitglieder beschlossen werden.</li>
      <li>Über die Beschlüsse der Mitgliederversammlung ist ein Protokoll anzufertigen, das von der / vom Versammlungsleitenden und der Protokollführerin bzw. dem Protokollführer zu unterzeichnen ist.</li>
      <li>Beschlüsse der Mitgliederversammlung können auch im Umlaufverfahren gefasst werden, sofern in dieser Satzung oder gesetzlich nichts anderes bestimmt ist; diese Beschlüsse können auch die Änderung der Satzung vorsehen. Hierzu hat der Antragsteller dem Vorstand seine Beschlussvorlage in Textform mitzuteilen; der Vorstand hat sie allen anderen Mitgliedern zu übermitteln. Die Beschlussvorlage gilt als angenommen, wenn ihr mehr als die Hälfte, bei Satzungsänderungen mindestens zwei Drittel der Mitglieder in Textform gegenüber dem Vorstand zustimmen; der Beschlussantrag zählt als zustimmendes Votum der oder des Antragstellenden. Kommt dieses Quorum nicht bis spätestens zum Ende des zehnten auf die Mitteilung des Antrags an die Mitglieder folgenden Werktages zustande, so gilt der Beschlussantrag als abgelehnt. Der Vorsitzende gibt das Ergebnis der Abstimmung allen übrigen Mitgliedern unverzüglich – spätestens nach Ablauf dieser Frist – in Textform bekannt. Erhebt ein Mitglied in Textform Widerspruch gegen die Richtigkeit des Ergebnisses, so entscheidet hierüber der Vorstand.</li>
      </ol>
      <h3 id="vorstand">§ 13 Vorstand</h3>
      <ol type="1">
      <li>Der Vorstand im Sinn des § 26 BGB besteht aus einem oder einer Vorsitzenden und zwei Beisitzenden.</li>
      <li>Die Mitglieder des Vorstands vertreten den Verein gerichtlich und außergerichtlich. Vorsitzende vertreten alleine, zwei Beisitzende vertreten gemeinsam. Jedes Vorstandsmitglied ist alleine empfangsbevollmächtigt. Der Vorstand beschließt einstimmig, welches Vorstandsmitglied die Kasse führt.</li>
      <li>(entfallen)</li>
      <li>Der Vorstand wird von der Mitgliederversammlung auf die Dauer von zwei Jahren gewählt. Wiederwahl ist zulässig. Vorstandsmitglieder können nur Mitglieder des Vereins werden.</li>
      <li>Der Vorstand bleibt solange im Amt, bis ein neuer Vorstand gewählt ist. Bei Beendigung der Mitgliedschaft im Verein endet auch das Amt als Vorstand.</li>
      </ol>
      <h3 id="beschlüsse-des-vorstands">§ 14 Beschlüsse des Vorstands</h3>
      <ol type="1">
      <li>Beschlüsse des Vorstands binden im Innenverhältnis alle Vorstandsmitglieder. Sie werden durch Abstimmung im Rahmen einer Vorstandssitzung oder im Umlaufverfahren gefasst.</li>
      <li>Soll ein Beschluss im Rahmen einer Vorstandssitzung gefasst werden, so entscheidet die einfache Mehrheit der abgegebenen Stimmen. Stimmenthaltungen und ungültige Stimmen bleiben außer Betracht. Bei Stimmengleichheit gibt die Stimme des Vorsitzenden den Ausschlag.</li>
      <li>Soll ein Beschluss im Umlaufverfahren gefasst werden, so hat die Antragstellerin bzw. der Antragsteller allen übrigen Vorstandsmitgliedern seine Beschlussvorlage in Textform mitzuteilen. Sie gilt als angenommen, wenn ihr mehr als die Hälfte der Vorstandsmitglieder in Textform gegenüber allen Vorstandsmitgliedern zustimmen; der Beschlussantrag zählt als zustimmendes Votum der bzw. des Antragstellenden. Kommt dieses Quorum nicht bis spätestens zum Ende des siebten auf die Antragstellung folgenden Werktages zustande, so gilt der Beschlussantrag als abgelehnt. Der Vorsitzende gibt das Ergebnis der Abstimmung allen übrigen Vorstandsmitgliedern unverzüglich in Textform bekannt, sobald alle Vorstandsmitglieder ihre Stimme abgegeben haben oder die Frist für die Stimmabgabe abgelaufen ist. Erhebt ein Vorstandsmitglied Widerspruch gegen die Richtigkeit des Ergebnisses, so entscheidet der Vorstand darüber unter Mitwirkung des Vorstandsmitglieds, das den Widerspruch erhebt, auf einer Vorstandssitzung.</li>
      <li>Zu den Einzelheiten der Beschlussfassung und zur weiteren Führung der Geschäfte kann sich der Vorstand durch einstimmigen Beschluss eine Geschäftsordnung geben.</li>
      </ol>
      <h3 id="kassenprüfung">§ 15 Kassenprüfung</h3>
      <ol type="1">
      <li>Die Mitgliederversammlung bestimmt die Art der Kassenprüfung. Soweit es der Umfang der Buchhaltung erlaubt, kann die Kasse auch unmittelbar im Rahmen der Mitgliederversammlung geprüft werden. Der Kassenprüfer bzw. die Kassenprüferin berichtet der Mitgliederversammlung über das Ergebnis der Kassenprüfung.</li>
      <li>Sofern ein(e) Kassenprüfer(in) bestimmt wird, darf diese(r) nicht Mitglied des Vorstands sein. Wiederwahl ist zulässig.</li>
      <li>Der Kassenprüfer hat die Kasse auch unabhängig von einer Mitgliederversammlung zu prüfen
      <ol type="a">
      <li>auf Wunsch des Vorstands;</li>
      <li>auf Wunsch eines Vorstandsmitglieds, wenn sich die Zusammensetzung des Vorstands verändert, oder</li>
      <li>in sonstigen Fällen, in denen im Interesse des Vereins Klarheit über die ordnungsgemäße Führung der Kasse zu schaffen ist.</li>
      </ol></li>
      </ol>
      <h3 id="auflösung-des-vereins">§ 16 Auflösung des Vereins</h3>
      <p>Bei Auflösung oder Aufhebung des Vereins oder bei Wegfall der steuerbegünstigten Zwecke fällt das Vermögen des Vereins an die Gesellschaft für Freiheitsrechte e.V., eingetragen in das Vereinsregister des Amtsgerichts Berlin-Charlottenburg unter VR 34505 B, der es unmittelbar und ausschließlich für gemeinnützige Zwecke zu verwenden hat, sofern dieser Verein noch besteht und noch als gemeinnützig anerkannt ist. Andernfalls fällt das Vermögen an eine andere vom Vorstand zu bestimmende juristische Person des öffentlichen Rechts oder eine andere steuerbegünstigte Körperschaft zwecks Verwendung für Zwecke der Förderung von Wissenschaft und Forschung, die das Vermögen des Vereins unmittelbar und ausschließlich für gemeinnützige Zwecke zu verwenden hat.</p>
    </v-container>
  </div>
</template>

<style scoped>
  div.logo-bg {
    position: absolute;
    bottom: 0;
    width: 50%;
    min-width: 300px;
    z-index: 1;
    right: 0;
    height: 100%;
    text-align: right;
    opacity: .1;
  }
  .triangle-fg {
    z-index: 2;
  }
  #satzung h3 {
    padding-top: 1em;
  }
</style>

<script>
export default {
  name: 'AboutPage',
  data: () => ({
    purposes: [
      {
        title: 'Data Security for the General Public',
        text: 'deSEC strives to achieve large-scale adoption of IT security techniques to the benefit of the general ' +
                'public, such as the automatic use of cryptography to guarantee connection authenticity and ' +
                'confidentiality.',
      },
      {
        title: 'DNS Hosting Service',
        text: 'As a contribution to the online security and privacy of the general public, we operate a publicly ' +
                'available, not-for-profit DNS hosting service with focus on data authenticity and usability.',
      },
      {
        title: 'Security Research',
        text: 'deSEC supports research in the area of secure communications. All research will be made publicly ' +
                'available in open access fashion, using responsible disclose procedures when indicated.',
      },
      {
        title: 'Networking',
        text: 'deSEC supports the community by organizing events for collaboration, networking, exchange, etc. All ' +
                'activities are funded by donations. Fees may only be charged as required to cover operational costs.',
      },
    ],
  })
}
</script>
