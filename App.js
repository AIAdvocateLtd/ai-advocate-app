
import React from 'react';
import { SafeAreaView, View, Text, Image, StyleSheet, TouchableOpacity } from 'react-native';
import { StatusBar } from 'expo-status-bar';

export default function App() {
  return (
    <SafeAreaView style={styles.container}>
      <StatusBar style="light" />
      <View style={styles.header}>
        <Image source={require('./assets/icon.png')} style={styles.logo} />
        <Text style={styles.title}>AI Advocate</Text>
      </View>
      <Text style={styles.headline}>Your AI Legal Partner - Anytime, Anywhere</Text>
      <Text style={styles.sub}>
        Instant legal guidance, document help, and court prep — all in your pocket.
      </Text>
      <TouchableOpacity style={styles.button}>
        <Text style={styles.buttonText}>Coming Soon on the App Store</Text>
      </TouchableOpacity>
      <View style={styles.cardRow}>
        {['Lex - Legal Copilot', 'Smart Legal Recorder', 'Courtroom Mode', 'My Legal Files'].map((t,i)=>(
          <View key={i} style={styles.card}><Text style={styles.cardTitle}>{t}</Text></View>
        ))}
      </View>
      <Text style={styles.footer}>© 2025 AI Advocate</Text>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex:1, backgroundColor:'#0A0A0A', padding:20, alignItems:'center' },
  header: { flexDirection:'row', alignItems:'center', marginTop:10 },
  logo: { width:44, height:44, marginRight:10 },
  title: { color:'#D4AF37', fontSize:20, fontWeight:'700' },
  headline: { color:'#fff', fontSize:22, fontWeight:'700', textAlign:'center', marginTop:20 },
  sub: { color:'#ddd', textAlign:'center', marginTop:8 },
  button: { backgroundColor:'#D4AF37', paddingVertical:12, paddingHorizontal:16, borderRadius:10, marginTop:16 },
  buttonText: { color:'#111', fontWeight:'700' },
  cardRow: { flexDirection:'row', flexWrap:'wrap', justifyContent:'center', marginTop:24 },
  card: { width:'45%', minHeight:80, backgroundColor:'#111315', borderWidth:1, borderColor:'#222', borderRadius:12, padding:10, margin:6 },
  cardTitle: { color:'#D4AF37', fontWeight:'700' },
  footer: { color:'#aaa', position:'absolute', bottom:16 }
});
