<?php

$auth = getAuthenticationDetails();

if ($auth === false) {
    header('WWW-Authenticate: Basic realm="dynDNS"');
    header('HTTP/1.0 401 Unauthorized');
    exit;
}

/**
 * Determines the IPv4 address for dynDNS update.
 */
function getIpv4Addr() {
    $ipv4_sources = [
        @$_REQUEST['myip'],
        @$_REQUEST['ip'],
        @$_REQUEST['dnsto'],
        @$_SERVER['REMOTE_ADDR'],
    ];

    foreach($ipv4_sources as $ip) {
      if ($ip) return $ip;
    }

    throw \Exception();
}

/**
 * Determines the credentials used
 */
function getAuthenticationDetails() {
    $headers = getallheaders();
    
    // Work around the fact that the following just produces NULL (on some machines):
    // if(isset($headers["Authorization"])) $authorization = $headers["Authorization"];
    foreach($headers as $key => $value) {
        if($key == "Authorization") {
            $authorization = $value;
            break;
        }
    }
    
    if(isset($authorization)) {
        $auth = explode(':', base64_decode(substr($authorization, strlen('Basic '))));
        
        if(isset($auth[1])) {
            return $auth;
        }
    }
    
    if (isset($_REQUEST['username']) && isset($_REQUEST['password'])) {
        $username = $_REQUEST['username'];
        $password = $_REQUEST['password'];
        
        if(!isset($_SERVER['HTTPS']) || !strlen($_SERVER['HTTPS'])) {
            $url = sprintf('https://%s/update?username=%s&password=%s', $_SERVER['HTTP_HOST'], urlencode($username), urlencode($password));
            header("HTTP/1.1 301 Moved Permanently");
            header("Location: $url");
            exit;
        }
        
        header('Strict-Transport-Security: max-age=31536000; includeSubDomains;');
        
        return [$username, $password];
    }
    
    return false;
}

$now = new DateTime();

$settings = [
    'token' => $auth[1],
    'domain' => $auth[0],
    'ip' => getIpv4Addr(),
];

$body = '{"arecord":"' . $settings['ip'] . '"}';

$ch = curl_init();
curl_setopt($ch, CURLOPT_URL, 'https://desec.io/api/domains/' . $settings['domain'] . '/');
curl_setopt($ch, CURLOPT_CUSTOMREQUEST, 'PATCH');
curl_setopt($ch, CURLOPT_HEADER, 1);
curl_setopt($ch, CURLOPT_RETURNTRANSFER, 1);
curl_setopt($ch, CURLOPT_HTTPHEADER, ['Authorization: Token ' . $settings['token'], 'Content-Type: application/json', 'Content-Length: ' . strlen($body)]);
curl_setopt($ch, CURLOPT_POSTFIELDS, $body);
$data = curl_exec($ch);
curl_close($ch);

$log  = '';
$log .= $now->format('c') . "\n\n";
$log .= print_r(json_decode(file_get_contents('php://input')), true) . "\n";
$log .= print_r($_REQUEST, true) . "\n";
$log .= print_r($auth, true) . "\n";
$log .= print_r($settings, true) . "\n";
$log .= print_r($data, true) . "\n";
$log .= "\n\n\n";

echo "<TITLE>success</TITLE>\n";
echo "return code: NOERROR\n";
echo "error code: NOERROR\n";
echo "Your hostname has been updated.\n";
