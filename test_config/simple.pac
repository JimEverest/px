// Simple PAC file for basic testing
function FindProxyForURL(url, host) {
    // Local addresses go direct
    if (isPlainHostName(host) || host == "127.0.0.1" || host == "localhost") {
        return "DIRECT";
    }
    
    // Everything else goes through proxy
    return "PROXY 127.0.0.1:33210; DIRECT";
}